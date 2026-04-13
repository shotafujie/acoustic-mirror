"""Energy-based voice activity detection (VAD).

Splits audio into 30ms frames, computes per-frame energy, estimates the
noise floor as the 10th percentile of recent frame energies, and classifies
frames as speech when energy exceeds noise floor + threshold.
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

_ENERGY_FLOOR = 1e-10  # avoid log10(0)


@dataclass
class SpeechResult:
    is_speech: bool
    speech_ratio: float
    noise_floor_db: float
    energy_db: float


def frame_energy_db(frame: np.ndarray) -> float:
    """Mean squared energy of a frame, in dB."""
    energy = float(np.mean(frame.astype(np.float64) ** 2))
    return 10.0 * np.log10(max(energy, _ENERGY_FLOOR))


class SpeechDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        threshold_db: float = 6.0,
    ) -> None:
        self._sample_rate = sample_rate
        self._frame_size = int(sample_rate * frame_ms / 1000)
        self._threshold_db = threshold_db
        # Keep ~5 seconds of frame energies for noise floor estimation
        max_frames = int(5000 / frame_ms)
        self._energy_history: deque[float] = deque(maxlen=max_frames)

    def _noise_floor_db(self) -> float:
        if not self._energy_history:
            return -80.0
        sorted_energies = sorted(self._energy_history)
        idx = max(0, int(len(sorted_energies) * 0.1) - 1)
        return sorted_energies[idx]

    def process(self, chunk: np.ndarray) -> SpeechResult:
        """Analyze a chunk and return speech activity result."""
        n_frames = len(chunk) // self._frame_size
        if n_frames == 0:
            nf = self._noise_floor_db()
            return SpeechResult(
                is_speech=False, speech_ratio=0.0, noise_floor_db=nf, energy_db=-80.0
            )

        frame_energies = []
        for i in range(n_frames):
            start = i * self._frame_size
            frame = chunk[start : start + self._frame_size]
            e = frame_energy_db(frame)
            frame_energies.append(e)
            self._energy_history.append(e)

        noise_floor = self._noise_floor_db()
        threshold = noise_floor + self._threshold_db

        speech_frames = sum(1 for e in frame_energies if e > threshold)
        speech_ratio = speech_frames / n_frames
        avg_energy = float(np.mean(frame_energies))

        return SpeechResult(
            is_speech=speech_ratio > 0.3,
            speech_ratio=speech_ratio,
            noise_floor_db=noise_floor,
            energy_db=avg_energy,
        )
