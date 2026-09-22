"""Entry point and pipeline orchestration.

Wires together audio capture, analysis modules, and servers to provide
real-time speech intelligibility monitoring.
"""

import asyncio
import argparse
import logging
import signal
import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np

from acoustic_mirror.analysis.cause_separator import CauseResult, CauseSeparator
from acoustic_mirror.analysis.room_profiler import (
    RoomProfile,
    RoomProfiler,
    estimate_early_to_late_ratio,
)
from acoustic_mirror.analysis.speech_detector import SpeechDetector, SpeechResult
from acoustic_mirror.analysis.srmr import SRMRProcessor
from acoustic_mirror.audio.buffer import RingBuffer
from acoustic_mirror.audio.capture import list_devices, open_stream
from acoustic_mirror.dashboard.http_server import DashboardServer
from acoustic_mirror.feedback.haptic_patterns import get_pattern
from acoustic_mirror.feedback.ws_server import WSBroadcaster

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 8000  # 500ms — VAD/RT60/DRR window (unchanged, see docs/adr/ADR-0002)
SRMR_WINDOW_SAMPLES = 3 * SAMPLE_RATE  # 3s — SRMR's own analysis window (ADR-0002)

# Gate thresholds for SRMR recomputation (ADR-0002). Initial values, tuned
# by feel rather than measurement; revisit if #10's harness or real usage
# shows they're off.
_SRMR_GATE_MIN_SPEECH_RATIO = 0.7
_SRMR_GATE_MIN_SECONDS_BETWEEN_COMPUTES = 1.0
_SRMR_HISTORY_LEN = 6  # 6 * 500ms = 3s, matching SRMR_WINDOW_SAMPLES


def should_recompute_srmr(
    recent_speech_ratio: float,
    seconds_since_last_compute: float,
    buffer_full: bool,
) -> bool:
    """Pure gate function deciding whether to recompute SRMR this tick.

    Kept free of state (ADR-0002) so the two independent conditions — how
    much of the recent window was speech, and how long since the last
    compute — can be reasoned about and tested without the caller's deques
    and timers.
    """
    if not buffer_full:
        return False
    if recent_speech_ratio < _SRMR_GATE_MIN_SPEECH_RATIO:
        return False
    return seconds_since_last_compute >= _SRMR_GATE_MIN_SECONDS_BETWEEN_COMPUTES


@dataclass
class AnalysisResult:
    timestamp: float
    speech_active: bool
    speech_ratio: float = 0.0
    noise_floor_db: float = -80.0
    energy_db: float = -80.0
    srmr_score: float | None = None
    srmr_age_seconds: float | None = None
    room_profile: RoomProfile | None = None
    cause: CauseResult | None = None
    haptic_pattern: dict | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "type": "feedback",
            "timestamp": self.timestamp,
            "speech_active": self.speech_active,
            "speech_ratio": self.speech_ratio,
            "noise_floor_db": round(self.noise_floor_db, 1),
            "energy_db": round(self.energy_db, 1),
        }
        if self.room_profile is not None:
            rp = self.room_profile
            d["room_profile"] = {
                "rt60": round(rp.rt60, 3),
                "noise_floor_db": round(rp.noise_floor_db, 1),
                "early_to_late_ratio_db": round(rp.early_to_late_ratio_db, 1),
                "room_type": rp.room_type.value,
                "srmr_target": rp.srmr_target,
                "rt60_confidence": round(rp.rt60_confidence, 2),
            }
        if self.srmr_score is not None and self.room_profile is not None:
            ratio = self.srmr_score / self.room_profile.srmr_target
            d["intelligibility_ratio"] = round(ratio, 3)
            d["overall"] = (
                "good" if ratio >= 0.8 else "warning" if ratio >= 0.5 else "alert"
            )
        if self.srmr_age_seconds is not None:
            d["srmr_age_seconds"] = round(self.srmr_age_seconds, 1)
        if self.cause is not None and self.cause.primary_cause is not None:
            d["primary_cause"] = {
                "cause": self.cause.primary_cause,
                "action": self.cause.action,
                "severity": round(self.cause.severity, 2),
                "haptic": self.haptic_pattern["name"] if self.haptic_pattern else None,
            }
        if self.haptic_pattern is not None:
            d["haptic_pattern"] = self.haptic_pattern
        return d


class AnalysisPipeline:
    """Orchestrates all analysis modules for a single audio chunk."""

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self._sample_rate = sample_rate
        self._speech_detector = SpeechDetector(sample_rate=sample_rate)
        self._room_profiler = RoomProfiler(sample_rate=sample_rate)
        self._srmr_processor = SRMRProcessor(sample_rate=sample_rate)
        self._cause_separator = CauseSeparator()
        self._prev_speech = False
        self._prev_chunk: np.ndarray | None = None
        self._prev_frame_energies: list[float] = []
        # Persist last speech-frame results so non-speech frames don't clear them
        self._last_srmr_score: float | None = None
        self._last_srmr_compute_time: float | None = None
        self._last_cause: CauseResult | None = None
        self._last_haptic: dict | None = None
        # Recent VAD history feeding the SRMR recompute gate (ADR-0002)
        self._srmr_speech_history: deque[bool] = deque(maxlen=_SRMR_HISTORY_LEN)

    def _find_speech_offset(self, frame_energies: list[float], threshold_db: float) -> int | None:
        """Find the last speech frame index (frame where energy drops below threshold)."""
        last_speech = None
        for i, e in enumerate(frame_energies):
            if e > threshold_db:
                last_speech = i
        return last_speech

    def _extract_decay_segment(self, chunk: np.ndarray, frame_energies: list[float]) -> np.ndarray | None:
        """Extract the decay tail from a chunk that contains a speech→silence transition."""
        if not frame_energies:
            return None
        threshold = self._speech_detector._noise_floor_db() + self._speech_detector._threshold_db
        offset_frame = self._find_speech_offset(frame_energies, threshold)
        if offset_frame is None:
            return None
        # Start from the frame after the last speech frame
        frame_size = self._speech_detector._frame_size
        start_sample = (offset_frame + 1) * frame_size
        if start_sample >= len(chunk):
            return None
        decay = chunk[start_sample:]
        # Need at least 100ms of decay (ADR-0003, revised): the decay tail
        # only ever comes from what's left of a single 500ms chunk after
        # the last speech frame, so a 300ms floor made this unreachable
        # for most utterance-end phases (offset_frame would have to fall
        # in the chunk's first ~6 of 16 frames). 100ms keeps enough frames
        # for a T20 fit to be attempted; estimate_rt60_from_decay's own
        # confidence gate (R^2 < 0.5 is dropped by RoomProfiler.update_rt60)
        # is what actually filters out decay observations too short or
        # noisy to trust, rather than an arbitrary length cutoff.
        if len(decay) < int(self._sample_rate * 0.1):
            return None
        return decay

    def _is_isolated_onset(self, onset_frame: int, frame_energies: list[float], threshold_db: float) -> bool:
        """True if no frame in the ~200ms preceding the onset was above the
        speech threshold (ADR-0003's isolated-onset gate). Without this,
        the "late" window of estimate_early_to_late_ratio can catch the
        previous syllable's direct sound rather than pure reverberant
        tail, in continuous speech.
        """
        isolation_ms = 200.0
        frame_ms = self._speech_detector._frame_size / self._sample_rate * 1000
        n_isolation_frames = max(1, round(isolation_ms / frame_ms))
        preceding = list(self._prev_frame_energies)[-n_isolation_frames:] + frame_energies[:onset_frame]
        return all(e <= threshold_db for e in preceding)

    def process(self, chunk: np.ndarray, srmr_window: np.ndarray | None = None) -> AnalysisResult:
        """Run one analysis tick.

        Args:
            chunk: the 500ms VAD/RT60/DRR window (unchanged cadence).
            srmr_window: the latest 3s SRMR window (ADR-0002), or None if
                the SRMR ring buffer hasn't filled yet. SRMR is only
                recomputed when this is provided AND the gate passes
                (see `should_recompute_srmr`); otherwise the last computed
                score/cause/haptic pattern are carried forward.
        """
        timestamp = time.time()

        # Step 1: Speech detection
        speech_result = self._speech_detector.process(chunk)

        # Update room profiler noise floor
        self._room_profiler.update_noise_floor(speech_result.noise_floor_db)

        # Detect speech→silence transition for RT60 estimation (Bug 1+2 fix)
        # Use the PREVIOUS chunk (which contained speech) to find the decay tail
        if self._prev_speech and not speech_result.is_speech and self._prev_chunk is not None:
            decay = self._extract_decay_segment(self._prev_chunk, self._prev_frame_energies)
            if decay is not None:
                self._room_profiler.update_rt60(decay)

        # Early-to-late ratio estimation on speech onset (Bug 5 fix; ADR-0003
        # restricts this to isolated onsets — see _is_isolated_onset)
        if not self._prev_speech and speech_result.is_speech:
            threshold = speech_result.noise_floor_db + self._speech_detector._threshold_db
            onset_frame = next(
                (i for i, e in enumerate(speech_result.frame_energies) if e > threshold),
                None,
            )
            if onset_frame is not None and self._is_isolated_onset(
                onset_frame, speech_result.frame_energies, threshold
            ):
                onset_sample = onset_frame * self._speech_detector._frame_size
                ratio = estimate_early_to_late_ratio(chunk, self._sample_rate, onset=onset_sample)
                self._room_profiler.update_early_to_late_ratio(ratio)

        self._prev_speech = speech_result.is_speech
        self._prev_chunk = chunk.copy()
        self._prev_frame_energies = speech_result.frame_energies

        room_profile = self._room_profiler.current_profile

        result = AnalysisResult(
            timestamp=timestamp,
            speech_active=speech_result.is_speech,
            speech_ratio=speech_result.speech_ratio,
            noise_floor_db=speech_result.noise_floor_db,
            energy_db=speech_result.energy_db,
            room_profile=room_profile,
        )

        # Step 2: gate + (maybe) recompute SRMR on the 3s window (ADR-0002)
        self._srmr_speech_history.append(speech_result.is_speech)
        recent_speech_ratio = sum(self._srmr_speech_history) / len(self._srmr_speech_history)
        seconds_since_last_compute = (
            float("inf")
            if self._last_srmr_compute_time is None
            else timestamp - self._last_srmr_compute_time
        )
        if should_recompute_srmr(
            recent_speech_ratio=recent_speech_ratio,
            seconds_since_last_compute=seconds_since_last_compute,
            buffer_full=srmr_window is not None,
        ):
            srmr_result = self._srmr_processor.process(srmr_window, is_speech=True)
            if srmr_result.is_valid:
                self._last_srmr_score = srmr_result.srmr_score
                self._last_srmr_compute_time = timestamp

                # Step 3: Cause separation (if below target)
                if srmr_result.srmr_score < room_profile.srmr_target:
                    cause = self._cause_separator.diagnose(
                        srmr_result.srmr_score,
                        room_profile.srmr_target,
                        room_profile,
                    )
                    self._last_cause = cause

                    # Step 4: Haptic pattern lookup
                    if cause.primary_cause is not None and cause.severity > 0.3:
                        try:
                            self._last_haptic = get_pattern(cause.primary_cause).to_dict()
                        except KeyError:
                            self._last_haptic = None
                    else:
                        self._last_haptic = None
                else:
                    # SRMR is good — clear persisted cause
                    self._last_cause = None
                    self._last_haptic = None

        # Persisted results (freshly computed above, or carried forward —
        # Bug 3 fix, now generalized to the gated recompute cadence).
        result.srmr_score = self._last_srmr_score
        result.cause = self._last_cause
        result.haptic_pattern = self._last_haptic
        result.srmr_age_seconds = (
            None if self._last_srmr_compute_time is None else timestamp - self._last_srmr_compute_time
        )

        return result


async def _run(args: argparse.Namespace) -> None:
    """Main async run loop."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(name)s %(message)s"
    )

    # Create components
    buf = RingBuffer(window_size=CHUNK_SAMPLES)
    srmr_buf = RingBuffer(window_size=SRMR_WINDOW_SAMPLES)
    pipeline = AnalysisPipeline(sample_rate=args.sample_rate)
    ws_broadcaster = WSBroadcaster(host="localhost", port=args.ws_port)

    # The broadcaster starts first so the dashboard can serve its real port
    # to the page (GET /api/config) instead of the page guessing one.
    await ws_broadcaster.start()
    dashboard = DashboardServer(
        host="localhost", port=args.http_port, ws_port=ws_broadcaster.port
    )
    dashboard.start()

    logger.info(
        f"Dashboard: http://localhost:{dashboard.port}?ws_port={ws_broadcaster.port}"
    )
    logger.info(f"WebSocket: ws://localhost:{ws_broadcaster.port}")

    # List devices
    if args.list_devices:
        print(list_devices())
        dashboard.stop()
        await ws_broadcaster.stop()
        return

    # Start audio capture
    stream = open_stream(
        vad_buffer=buf,
        srmr_buffer=srmr_buf,
        device=args.device,
        sample_rate=args.sample_rate,
        block_size=512,
    )
    stream.start()
    logger.info("Audio capture started")

    # Shutdown event
    stop = asyncio.Event()

    def _signal_handler():
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # Analysis loop
    try:
        while not stop.is_set():
            if buf.has_enough_data:
                chunk = buf.get_window()
                srmr_window = srmr_buf.get_window() if srmr_buf.has_enough_data else None
                result = pipeline.process(chunk, srmr_window=srmr_window)
                await ws_broadcaster.broadcast(result.to_dict())
            await asyncio.sleep(0.5)  # 500ms interval
    finally:
        logger.info("Shutting down...")
        stream.stop()
        stream.close()
        await ws_broadcaster.stop()
        dashboard.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Acoustic Speech Monitor")
    parser.add_argument("--device", type=int, default=None, help="Audio input device ID")
    parser.add_argument("--sample-rate", type=int, default=SAMPLE_RATE, help="Sample rate (Hz)")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--http-port", type=int, default=8080, help="Dashboard HTTP port")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices and exit")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
