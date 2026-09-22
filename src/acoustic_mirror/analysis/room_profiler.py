"""Blind room acoustic estimation — RT60, noise floor, early/late energy
ratio, room classification.

Estimates room parameters from speech signals without external measurement
equipment, using Schroeder-integral energy decay analysis for RT60 and
onset-based energy splitting for an early-to-late energy ratio proxy.

See docs/adr/ADR-0003 for why RT60 uses a Schroeder integral + T20 fit
rather than a direct dB regression, and why the DRR-like measure is named
"early-to-late ratio" rather than DRR (it isn't the impulse-response DRR —
continuous speech's next syllable can land in the "late" window).
"""

from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy import stats

_DEFAULT_RT60 = 0.2  # stands in for an unmeasured room (ADR-0005)
_RT60_MIN = 0.05
_RT60_MAX = 3.0
_RT60_CONFIDENCE_MIN = 0.5  # below this R^2, don't trust the fit (ADR-0003)
# Frames dropped from the Schroeder integral's tail before fitting, as a
# FIXED duration rather than a fraction of the window (ADR-0003, revised
# after advisor review). The integral's truncation knee — where the curve
# collapses because there's no more future energy to accumulate — has a
# roughly fixed absolute extent regardless of window length; a
# proportional trim protects short windows far less than long ones (at a
# 100ms window a 15% trim drops one 10ms frame, leaving the knee to
# dominate most of the T20 fit — verified to produce a biased-short
# estimate at HIGH confidence, which the R^2 gate does not catch on its
# own). A fixed trim makes short windows self-reject via insufficient T20
# coverage instead of returning a confidently wrong number.
_RT60_SCHROEDER_TAIL_TRIM_MS = 50.0
_EARLY_TO_LATE_FLOOR = 1e-10  # avoid log10(0)


class RoomType(Enum):
    """Room classification with associated SRMR target values."""

    QUIET_SMALL = "quiet_small"
    NOISY_SMALL = "noisy_small"
    MEDIUM_ROOM = "medium_room"
    NOISY_MEDIUM = "noisy_medium"
    REVERBERANT = "reverberant"
    REVERBERANT_NOISY = "reverberant_noisy"

    @property
    def srmr_target(self) -> float:
        return _SRMR_TARGETS[self]


# Calibrated against this repo's own SRMR implementation (docs/adr/ADR-0001)
# — NOT against SRMRpy or literature values, which use a different scale.
# Measured with tests/synth.py's synth_speech()/apply_reverb() over a 3s
# window (ADR-0002) after the anti-aliasing (#4) and windowing (#5) fixes,
# averaged over 5 seeds per RT60 condition (mean ± std):
#
#   RT60    SRMR (mean ± std, n=5)
#   Dry     3.421 ± 0.082
#   0.16s   3.194 ± 0.130
#   0.36s   2.170 ± 0.098
#   0.61s   1.363 ± 0.067
#   1.0s    0.791 ± 0.044
#
# QUIET_SMALL/MEDIUM_ROOM/REVERBERANT targets are set at the measured mean
# score for a representative RT60 in that room type's range (see
# classify_room), so a typical recording for that room type lands near
# ratio=1.0. NOISY variants aren't directly measured (this harness only
# varies RT60, not additive noise) — they keep the same relative discount
# from their quiet counterpart as the pre-calibration values did
# (~0.65-0.7x), since SRMR is a reverberation/modulation metric and
# doesn't react directly to additive noise floor the way it does to RT60.
_SRMR_TARGETS = {
    RoomType.QUIET_SMALL: 3.3,  # ~ mean(Dry, 0.16s)
    RoomType.NOISY_SMALL: 2.3,
    RoomType.MEDIUM_ROOM: 2.2,  # ~ 0.36s
    RoomType.NOISY_MEDIUM: 1.4,
    RoomType.REVERBERANT: 1.1,  # ~ mean(0.61s, 1.0s)
    RoomType.REVERBERANT_NOISY: 0.7,
}


@dataclass
class RoomProfile:
    rt60: float
    noise_floor_db: float
    early_to_late_ratio_db: float
    room_type: RoomType
    srmr_target: float
    rt60_confidence: float = 0.0


@dataclass
class RT60Estimate:
    rt60: float
    confidence: float  # R^2 of the T20 regression fit
    is_valid: bool


def estimate_rt60_from_decay(decay_signal: np.ndarray, sample_rate: int) -> RT60Estimate:
    """Estimate RT60 from an energy decay curve via Schroeder integration.

    Computes 10ms frame energies, then a Schroeder (reverse cumulative sum)
    integral over those frames — smoother than raw frame energy and less
    sensitive to a single loud/quiet frame. Fits a line to the T20 portion
    (-5dB to -25dB below the integral's peak) of the integrated curve in dB
    and extrapolates to -60dB.

    The last _RT60_SCHROEDER_TAIL_TRIM_MS of frames are dropped before
    fitting: the Schroeder integral necessarily collapses toward zero at
    the end of a truncated observation window (there's no more energy left
    to accumulate), producing a smooth, high-R^2 but biased-steep knee that
    the confidence gate alone would not catch (see docs/adr/ADR-0003). This
    trim is a fixed duration, not a fraction of the window — the knee's
    extent doesn't shrink with the window, so a short window needs the same
    absolute protection a long one does.
    """
    signal = decay_signal.astype(np.float64)

    # Compute energy in short frames (10ms)
    frame_size = max(1, int(sample_rate * 0.01))
    n_frames = len(signal) // frame_size
    if n_frames < 3:
        return RT60Estimate(rt60=_RT60_MAX, confidence=0.0, is_valid=False)

    energies = np.array(
        [
            np.mean(signal[i * frame_size : (i + 1) * frame_size] ** 2)
            for i in range(n_frames)
        ]
    )

    # Schroeder integral: reverse cumulative sum of frame energies, applied
    # to the small (n_frames-length) frame-energy array, not the raw
    # waveform — see docs/adr/ADR-0003.
    schroeder = np.cumsum(energies[::-1])[::-1]

    trim = max(1, int(_RT60_SCHROEDER_TAIL_TRIM_MS / 10))  # frame_size is fixed at 10ms
    schroeder = schroeder[: n_frames - trim]
    n_frames_trimmed = len(schroeder)
    if n_frames_trimmed < 3:
        return RT60Estimate(rt60=_RT60_MAX, confidence=0.0, is_valid=False)

    schroeder_db = 10.0 * np.log10(np.maximum(schroeder, 1e-10))
    peak_db = schroeder_db[0]  # monotonically non-increasing by construction

    # T20: -5dB to -25dB below peak, avoiding both the near-peak region
    # (onset transient) and the noise-floor-contaminated tail.
    mask = (schroeder_db <= peak_db - 5) & (schroeder_db >= peak_db - 25)
    if np.sum(mask) < 3:
        return RT60Estimate(rt60=_RT60_MAX, confidence=0.0, is_valid=False)

    t = np.arange(n_frames_trimmed) * frame_size / sample_rate
    t_fit = t[mask]
    e_fit = schroeder_db[mask]

    slope, _, rvalue, _, _ = stats.linregress(t_fit, e_fit)
    confidence = float(rvalue**2)

    if slope >= 0:
        return RT60Estimate(rt60=_RT60_MAX, confidence=confidence, is_valid=False)

    # RT60 = time for 60dB decay = -60 / slope
    rt60 = float(np.clip(-60.0 / slope, _RT60_MIN, _RT60_MAX))
    return RT60Estimate(rt60=rt60, confidence=confidence, is_valid=True)


def estimate_early_to_late_ratio(
    signal: np.ndarray,
    sample_rate: int,
    onset: int,
    early_ms: float = 50.0,
    late_ms: float = 200.0,
) -> float:
    """Estimate an onset-relative early-to-late energy ratio.

    NOT the impulse-response Direct-to-Reverberant Ratio (DRR) — this is a
    speech-onset proxy: ratio = 10*log10(energy_early / energy_late) where
    early is 0-50ms and late is 50-200ms after onset. In continuous speech
    the "late" window can contain the next syllable's direct sound rather
    than pure reverberant tail, so callers should only invoke this on
    isolated onsets (preceded by genuine silence) — see
    docs/adr/ADR-0003 and AnalysisPipeline's isolated-onset gate.
    """
    early_samples = int(sample_rate * early_ms / 1000)
    late_samples = int(sample_rate * late_ms / 1000)

    early_end = min(onset + early_samples, len(signal))
    late_end = min(onset + late_samples, len(signal))

    early_energy = float(np.sum(signal[onset:early_end].astype(np.float64) ** 2))
    late_energy = float(
        np.sum(signal[early_end:late_end].astype(np.float64) ** 2)
    )

    early_energy = max(early_energy, _EARLY_TO_LATE_FLOOR)
    late_energy = max(late_energy, _EARLY_TO_LATE_FLOOR)

    return 10.0 * np.log10(early_energy / late_energy)


def classify_room(rt60: float, noise_floor_db: float) -> RoomType:
    """Classify room type from RT60 and noise floor.

    Thresholds from the design document:
      RT60 < 0.25s: small, 0.25-0.6s: medium, >= 0.6s: reverberant
      noise < -40dB: quiet, >= -40dB (small) or -30dB (medium/large): noisy
    """
    if rt60 < 0.25:
        return RoomType.NOISY_SMALL if noise_floor_db >= -40 else RoomType.QUIET_SMALL
    elif rt60 < 0.6:
        return RoomType.NOISY_MEDIUM if noise_floor_db >= -30 else RoomType.MEDIUM_ROOM
    else:
        return (
            RoomType.REVERBERANT_NOISY
            if noise_floor_db >= -30
            else RoomType.REVERBERANT
        )


class RoomProfiler:
    """Stateful room acoustic estimator.

    Accumulates RT60 estimates across speech-offset events (median of recent
    estimates) and tracks noise floor and the early-to-late energy ratio.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        # Set by the rolling estimator (ADR-0005); None until enough decay
        # events agree. The pool and the aggregation live there now.
        self._rt60: float | None = None
        self._rt60_confidence: float = 0.0
        self._noise_floor_db = -60.0
        self._early_to_late_ratio_db = 10.0  # default: assume close distance

    @property
    def current_profile(self) -> RoomProfile:
        # classify_room needs a number; _DEFAULT_RT60 stands in while the
        # room is unmeasured. rt60_confidence is what says which it is —
        # the dashboard refuses to draw a value at confidence 0 (ADR-0005).
        rt60 = self._rt60 if self._rt60 is not None else _DEFAULT_RT60
        room_type = classify_room(rt60, self._noise_floor_db)
        return RoomProfile(
            rt60=rt60,
            noise_floor_db=self._noise_floor_db,
            early_to_late_ratio_db=self._early_to_late_ratio_db,
            room_type=room_type,
            srmr_target=room_type.srmr_target,
            rt60_confidence=self._rt60_confidence,
        )

    def set_rt60(self, rt60: float | None, confidence: float) -> None:
        """Record the rolling estimator's current view (ADR-0005).

        None means too few decay events have been observed to name a value —
        the profile then reports _DEFAULT_RT60 with confidence 0, and the
        dashboard shows no number rather than a plausible-looking one.
        """
        self._rt60 = rt60
        self._rt60_confidence = confidence if rt60 is not None else 0.0

    def update_noise_floor(self, noise_floor_db: float) -> None:
        self._noise_floor_db = noise_floor_db

    def update_early_to_late_ratio(self, ratio_db: float) -> None:
        self._early_to_late_ratio_db = ratio_db
