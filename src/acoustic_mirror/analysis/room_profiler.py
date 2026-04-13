"""Blind room acoustic estimation — RT60, noise floor, DRR, room classification.

Estimates room parameters from speech signals without external measurement
equipment, using energy decay analysis (Ratnam et al. 2003) for RT60 and
onset-based energy splitting for DRR.
"""

from collections import deque
from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy import stats

_RT60_MIN = 0.05
_RT60_MAX = 3.0
_DRR_FLOOR = 1e-10  # avoid log10(0)


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


_SRMR_TARGETS = {
    RoomType.QUIET_SMALL: 5.0,
    RoomType.NOISY_SMALL: 3.5,
    RoomType.MEDIUM_ROOM: 4.0,
    RoomType.NOISY_MEDIUM: 2.5,
    RoomType.REVERBERANT: 3.0,
    RoomType.REVERBERANT_NOISY: 2.0,
}


@dataclass
class RoomProfile:
    rt60: float
    noise_floor_db: float
    drr_db: float
    room_type: RoomType
    srmr_target: float


def estimate_rt60_from_decay(decay_signal: np.ndarray, sample_rate: int) -> float:
    """Estimate RT60 from an energy decay curve using linear regression in dB.

    Fits a line to the log-energy envelope and extrapolates to -60dB.
    """
    signal = decay_signal.astype(np.float64)

    # Compute energy in short frames (10ms)
    frame_size = max(1, int(sample_rate * 0.01))
    n_frames = len(signal) // frame_size
    if n_frames < 3:
        return _RT60_MAX

    energies = np.array(
        [
            np.mean(signal[i * frame_size : (i + 1) * frame_size] ** 2)
            for i in range(n_frames)
        ]
    )

    # Convert to dB, floor at -100
    energies_db = 10.0 * np.log10(np.maximum(energies, 1e-10))

    # Use only the portion from peak to -30dB below peak for robust fitting
    peak_db = np.max(energies_db)
    mask = energies_db >= peak_db - 30
    if np.sum(mask) < 3:
        return _RT60_MAX

    t = np.arange(n_frames) * frame_size / sample_rate
    t_fit = t[mask]
    e_fit = energies_db[mask]

    # Linear regression: energy_db = slope * t + intercept
    slope, _, _, _, _ = stats.linregress(t_fit, e_fit)

    if slope >= 0:
        return _RT60_MAX

    # RT60 = time for 60dB decay = -60 / slope
    rt60 = -60.0 / slope
    return float(np.clip(rt60, _RT60_MIN, _RT60_MAX))


def estimate_drr(
    signal: np.ndarray,
    sample_rate: int,
    onset: int,
    early_ms: float = 50.0,
    late_ms: float = 200.0,
) -> float:
    """Estimate Direct-to-Reverberant Ratio from onset-relative energy.

    DRR = 10 * log10(energy_early / energy_late) where early is 0-50ms
    and late is 50-200ms after onset.
    """
    early_samples = int(sample_rate * early_ms / 1000)
    late_samples = int(sample_rate * late_ms / 1000)

    early_end = min(onset + early_samples, len(signal))
    late_end = min(onset + late_samples, len(signal))

    early_energy = float(np.sum(signal[onset:early_end].astype(np.float64) ** 2))
    late_energy = float(
        np.sum(signal[early_end:late_end].astype(np.float64) ** 2)
    )

    early_energy = max(early_energy, _DRR_FLOOR)
    late_energy = max(late_energy, _DRR_FLOOR)

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
    estimates) and tracks noise floor and DRR.
    """

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._rt60_estimates: deque[float] = deque(maxlen=5)
        self._noise_floor_db = -60.0
        self._drr_db = 10.0  # default: assume close distance

    @property
    def current_profile(self) -> RoomProfile:
        rt60 = float(np.median(self._rt60_estimates)) if self._rt60_estimates else 0.2
        room_type = classify_room(rt60, self._noise_floor_db)
        return RoomProfile(
            rt60=rt60,
            noise_floor_db=self._noise_floor_db,
            drr_db=self._drr_db,
            room_type=room_type,
            srmr_target=room_type.srmr_target,
        )

    def update_rt60(self, decay_segment: np.ndarray) -> None:
        """Add an RT60 estimate from a speech-offset decay segment."""
        rt60 = estimate_rt60_from_decay(decay_segment, self._sample_rate)
        self._rt60_estimates.append(rt60)

    def update_noise_floor(self, noise_floor_db: float) -> None:
        self._noise_floor_db = noise_floor_db

    def update_drr(self, drr_db: float) -> None:
        self._drr_db = drr_db
