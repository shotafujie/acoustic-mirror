"""Synthetic speech/RIR generators shared by validity tests and ADR-0001's
threshold calibration measurement (docs/adr/ADR-0001, #10).
"""

import numpy as np

SAMPLE_RATE = 16000


def synth_speech(dur: float = 3.0, sample_rate: int = SAMPLE_RATE, seed: int = 42) -> np.ndarray:
    """4Hz-modulated noise simulating a speech temporal envelope."""
    rng = np.random.default_rng(seed)
    n = int(sample_rate * dur)
    t = np.arange(n, dtype=np.float64) / sample_rate
    noise = rng.standard_normal(n)
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 4 * t))
    return (0.3 * noise * envelope).astype(np.float32)


def synth_rir(rt60: float, sample_rate: int = SAMPLE_RATE, dur: float = 1.0, seed: int = 0) -> np.ndarray:
    """Exponentially decaying noise impulse response with the given RT60."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(sample_rate * dur)) / sample_rate
    h = rng.standard_normal(len(t)) * np.exp(-6.9078 * t / rt60)
    h[0] += 1.0
    return h.astype(np.float32)


def apply_reverb(speech: np.ndarray, rt60: float, sample_rate: int = SAMPLE_RATE, seed: int = 0) -> np.ndarray:
    """Convolve speech with a synthetic RIR, truncated to the original length and peak-normalized."""
    rir = synth_rir(rt60, sample_rate=sample_rate, seed=seed)
    wet = np.convolve(speech, rir)[: len(speech)]
    peak = np.max(np.abs(wet))
    if peak > 0:
        wet = wet / peak
    return wet.astype(np.float32)
