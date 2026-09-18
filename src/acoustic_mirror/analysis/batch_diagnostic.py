"""One-shot diagnostic over a whole recorded clip (docs/adr/ADR-0004).

The streaming pipeline can only ever see one decay tail per speech offset,
cut to what's left of a single 500ms chunk (ADR-0003). With the whole clip
in hand, this module instead collects every decay event it can find, fits
each with the same Schroeder/T20 estimator and confidence gate, and
aggregates by percentile — MicrophoneTest's approach, on our estimator.

Stateless by design: nothing here touches RoomProfiler's streaming state.
"""

from dataclasses import dataclass, field
from math import gcd

import numpy as np
from scipy.signal import resample_poly

from acoustic_mirror.analysis.cause_separator import CauseResult, CauseSeparator
from acoustic_mirror.analysis.room_profiler import (
    _RT60_CONFIDENCE_MIN,
    RoomProfile,
    classify_room,
    estimate_early_to_late_ratio,
    estimate_rt60_from_decay,
)
from acoustic_mirror.analysis.speech_detector import frame_energy_db
from acoustic_mirror.analysis.srmr import SRMRProcessor

SAMPLE_RATE = 16000
MIN_DURATION_SECONDS = 3.0  # SRMR's analysis window (ADR-0002)

# Decay-event detection on 10ms frames (ADR-0004). 10ms matches
# estimate_rt60_from_decay's own framing.
_EVENT_FRAME_MS = 10
_SPEECH_LEVEL_PERCENTILE = 95
_ORIGIN_WITHIN_DB = 10.0  # decay origin must be within this of speech level
_PLATEAU_DB = 3.0  # origin moves to the last frame within this of the event max
_REBOUND_DB = 3.0  # a rise above the running min by more than this ends the event
_MIN_EVENT_SECONDS = 0.1

_RT60_PERCENTILE = 70  # chosen over 50 by prototyping (ADR-0004)
_MIN_RT60_EVENTS = 3

# VAD on 30ms frames, same framing/margin as SpeechDetector's defaults, but
# with the noise floor taken from the whole clip at once — SpeechDetector's
# adaptive floor hasn't converged at the start of a clip.
_VAD_FRAME_MS = 30
_NOISE_FLOOR_PERCENTILE = 10
_SPEECH_THRESHOLD_DB = 6.0
_ISOLATION_MS = 200.0  # ADR-0003's isolated-onset gate
# Same value as main._SRMR_GATE_MIN_SPEECH_RATIO (ADR-0002); not imported
# because main pulls in audio I/O.
_SRMR_MIN_SPEECH_RATIO = 0.7

# RoomProfiler's defaults, used when a metric can't be estimated.
_DEFAULT_RT60 = 0.2
_DEFAULT_EARLY_TO_LATE_DB = 10.0


@dataclass
class DiagnosticResult:
    duration_seconds: float
    noise_floor_db: float
    speech_ratio: float
    rt60: float | None
    rt60_events: list[float]
    rt60_rejected_count: int
    early_to_late_ratio_db: float | None
    early_to_late_event_count: int
    srmr_score: float | None
    room_profile: RoomProfile
    cause: CauseResult | None = None
    defaulted_metrics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        rp = self.room_profile
        d: dict = {
            "type": "diagnostic",
            "duration_seconds": round(self.duration_seconds, 2),
            "noise_floor_db": round(self.noise_floor_db, 1),
            "speech_ratio": round(self.speech_ratio, 3),
            "rt60": {
                "value": None if self.rt60 is None else round(self.rt60, 3),
                "events": [round(v, 3) for v in self.rt60_events],
                "rejected_count": self.rt60_rejected_count,
            },
            "early_to_late_ratio": {
                "value_db": (
                    None
                    if self.early_to_late_ratio_db is None
                    else round(self.early_to_late_ratio_db, 1)
                ),
                "event_count": self.early_to_late_event_count,
            },
            "srmr_score": None if self.srmr_score is None else round(self.srmr_score, 3),
            "room_profile": {
                "rt60": round(rp.rt60, 3),
                "noise_floor_db": round(rp.noise_floor_db, 1),
                "early_to_late_ratio_db": round(rp.early_to_late_ratio_db, 1),
                "room_type": rp.room_type.value,
                "srmr_target": rp.srmr_target,
            },
            "defaulted_metrics": list(self.defaulted_metrics),
        }
        if self.srmr_score is not None:
            ratio = self.srmr_score / rp.srmr_target
            d["intelligibility_ratio"] = round(ratio, 3)
            d["overall"] = "good" if ratio >= 0.8 else "warning" if ratio >= 0.5 else "alert"
        if self.cause is not None and self.cause.primary_cause is not None:
            d["primary_cause"] = {
                "cause": self.cause.primary_cause,
                "action": self.cause.action,
                "severity": round(self.cause.severity, 2),
            }
        return d


def _frame_energies_db(signal: np.ndarray, frame_size: int) -> np.ndarray:
    n = len(signal) // frame_size
    return np.array([frame_energy_db(signal[i * frame_size : (i + 1) * frame_size]) for i in range(n)])


def find_decay_events(signal: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
    """Return (start, end) sample ranges of free-decay events (ADR-0004).

    Origin: a local energy maximum within _ORIGIN_WITHIN_DB of speech level,
    moved forward to the last frame still within _PLATEAU_DB of the event's
    max, so the source's own flat plateau isn't fitted as decay.
    End: energy reaching noise floor + _SPEECH_THRESHOLD_DB, or rebounding
    by more than _REBOUND_DB above the running minimum (next utterance).
    """
    frame_size = int(sample_rate * _EVENT_FRAME_MS / 1000)
    e = _frame_energies_db(signal, frame_size)
    n = len(e)
    if n < 3:
        return []
    floor = float(np.percentile(e, _NOISE_FLOOR_PERCENTILE))
    level = float(np.percentile(e, _SPEECH_LEVEL_PERCENTILE))
    if level - floor < _ORIGIN_WITHIN_DB:
        return []  # no speech standing out from the floor
    stop_db = floor + _SPEECH_THRESHOLD_DB
    min_frames = round(_MIN_EVENT_SECONDS * 1000 / _EVENT_FRAME_MS)

    events: list[tuple[int, int]] = []
    i = 1
    while i < n - 1:
        is_origin = e[i] >= level - _ORIGIN_WITHIN_DB and e[i] >= e[i - 1] and e[i] > e[i + 1]
        if not is_origin:
            i += 1
            continue
        j = i + 1
        running_min = e[i]
        while j < n and e[j] > stop_db and e[j] <= running_min + _REBOUND_DB:
            running_min = min(running_min, e[j])
            j += 1
        seg = e[i:j]
        start = i + int(np.flatnonzero(seg >= seg.max() - _PLATEAU_DB)[-1])
        if j - start >= min_frames:
            events.append((start * frame_size, j * frame_size))
        i = j + 1
    return events


def _vad(signal: np.ndarray, sample_rate: int) -> tuple[np.ndarray, float, int]:
    frame_size = int(sample_rate * _VAD_FRAME_MS / 1000)
    e = _frame_energies_db(signal, frame_size)
    floor = float(np.percentile(e, _NOISE_FLOOR_PERCENTILE))
    return e > floor + _SPEECH_THRESHOLD_DB, floor, frame_size


def _isolated_onsets(is_speech: np.ndarray) -> list[int]:
    n_iso = max(1, round(_ISOLATION_MS / _VAD_FRAME_MS))
    return [
        i
        for i in range(n_iso, len(is_speech))
        if is_speech[i] and not is_speech[i - n_iso : i].any()
    ]


def _to_16k(signal: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == SAMPLE_RATE:
        return signal.astype(np.float32)
    g = gcd(SAMPLE_RATE, sample_rate)
    return resample_poly(signal.astype(np.float64), SAMPLE_RATE // g, sample_rate // g).astype(np.float32)


def diagnose(signal: np.ndarray, sample_rate: int) -> DiagnosticResult:
    """Analyze a whole mono clip. Raises ValueError if shorter than MIN_DURATION_SECONDS."""
    duration = len(signal) / sample_rate
    if duration < MIN_DURATION_SECONDS:
        raise ValueError(f"clip is {duration:.2f}s; need at least {MIN_DURATION_SECONDS}s")
    y = _to_16k(signal, sample_rate)
    sr = SAMPLE_RATE
    defaulted: list[str] = []

    # RT60: every decay event, gated like the streaming path, then percentile
    rt60_events: list[float] = []
    rejected = 0
    for start, end in find_decay_events(y, sr):
        est = estimate_rt60_from_decay(y[start:end], sr)
        if est.is_valid and est.confidence >= _RT60_CONFIDENCE_MIN:
            rt60_events.append(est.rt60)
        else:
            rejected += 1
    rt60 = (
        float(np.percentile(rt60_events, _RT60_PERCENTILE))
        if len(rt60_events) >= _MIN_RT60_EVENTS
        else None
    )
    if rt60 is None:
        defaulted.append("rt60")

    # Early-to-late ratio: median over isolated onsets
    is_speech, noise_floor_db, vad_frame = _vad(y, sr)
    ratios = [estimate_early_to_late_ratio(y, sr, onset=i * vad_frame) for i in _isolated_onsets(is_speech)]
    early_to_late = float(np.median(ratios)) if ratios else None
    if early_to_late is None:
        defaulted.append("early_to_late_ratio")

    speech_ratio = float(is_speech.mean()) if len(is_speech) else 0.0

    room_rt60 = rt60 if rt60 is not None else _DEFAULT_RT60
    room_type = classify_room(room_rt60, noise_floor_db)
    profile = RoomProfile(
        rt60=room_rt60,
        noise_floor_db=noise_floor_db,
        early_to_late_ratio_db=early_to_late if early_to_late is not None else _DEFAULT_EARLY_TO_LATE_DB,
        room_type=room_type,
        srmr_target=room_type.srmr_target,
    )

    srmr_score = None
    cause = None
    if speech_ratio >= _SRMR_MIN_SPEECH_RATIO:
        srmr = SRMRProcessor(sample_rate=sr).process(y, is_speech=True)
        if srmr.is_valid:
            srmr_score = srmr.srmr_score
            if srmr_score < profile.srmr_target:
                cause = CauseSeparator().diagnose(srmr_score, profile.srmr_target, profile)

    return DiagnosticResult(
        duration_seconds=duration,
        noise_floor_db=noise_floor_db,
        speech_ratio=speech_ratio,
        rt60=rt60,
        rt60_events=rt60_events,
        rt60_rejected_count=rejected,
        early_to_late_ratio_db=early_to_late,
        early_to_late_event_count=len(ratios),
        srmr_score=srmr_score,
        room_profile=profile,
        cause=cause,
        defaulted_metrics=defaulted,
    )
