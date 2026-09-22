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


def synth_utterances(
    dur: float = 7.0,
    burst: float = 0.3,
    gap: float = 0.7,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 1,
) -> np.ndarray:
    """Noise bursts separated by silences of ~`gap` seconds (±20%).

    Unlike synth_speech (continuous modulated noise), this has genuine
    pauses between "utterances" so free reverberant decays can be observed —
    what the batch diagnostic's multi-event RT60 estimate needs (ADR-0004).
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(int(sample_rate * dur))
    t = 0.2
    while t + burst < dur:
        a, b = int(t * sample_rate), int((t + burst) * sample_rate)
        x[a:b] = 0.3 * rng.standard_normal(b - a)
        t += burst + gap * rng.uniform(0.8, 1.2)
    return x.astype(np.float32)


def reverberant_utterances(
    rt60: float,
    gap: float = 0.7,
    noise_db: float = -60.0,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 1,
) -> np.ndarray:
    """synth_utterances convolved with a synthetic RIR, peak-normalized, plus
    a white-noise floor at `noise_db` dBFS (ADR-0004's validity harness).

    The RIR is 1.5x RT60 long (min 1s) so its own truncation stays below
    the T20 fit range even for long RT60.
    """
    x = synth_utterances(gap=gap, sample_rate=sample_rate, seed=seed)
    rir = synth_rir(rt60, sample_rate=sample_rate, dur=max(1.0, rt60 * 1.5), seed=seed)
    y = np.convolve(x, rir)[: len(x)]
    y = y / np.max(np.abs(y))
    y = y + 10 ** (noise_db / 20) * np.random.default_rng(99).standard_normal(len(y))
    return y.astype(np.float32)


def speech_utterances(
    dur: float = 7.0,
    burst: float = 1.5,
    gap: float = 1.0,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 1,
) -> np.ndarray:
    """Utterances of speech-like modulated noise separated by pauses.

    `synth_utterances` fills its bursts with white noise, which has no
    speech envelope for SRMR to measure. ADR-0004's SRMR-gate revision
    rests on how much the pauses move SRMR, so its bursts have to carry
    one: each is a `synth_speech` segment.
    """
    rng = np.random.default_rng(seed)
    x = np.zeros(int(sample_rate * dur), dtype=np.float32)
    t = 0.2
    while t + burst < dur:
        a, b = int(t * sample_rate), int((t + burst) * sample_rate)
        x[a:b] = synth_speech(dur=burst, sample_rate=sample_rate, seed=int(t * 100) + 1)[: b - a]
        t += burst + gap * rng.uniform(0.9, 1.1)
    return x


def reverberant_speech(
    rt60: float,
    dur: float = 7.0,
    burst: float = 1.5,
    gap: float = 1.0,
    noise_db: float = -60.0,
    sample_rate: int = SAMPLE_RATE,
    seed: int = 1,
) -> np.ndarray:
    """`speech_utterances` in a room of the given RT60, with a noise floor.

    The pause-containing counterpart to `apply_reverb(synth_speech(...))`,
    which is the same room heard without pauses.
    """
    x = speech_utterances(dur=dur, burst=burst, gap=gap, sample_rate=sample_rate, seed=seed)
    rir = synth_rir(rt60, sample_rate=sample_rate, dur=max(1.0, rt60 * 1.5), seed=seed)
    y = np.convolve(x, rir)[: len(x)]
    y = y / np.max(np.abs(y))
    y = y + 10 ** (noise_db / 20) * np.random.default_rng(99).standard_normal(len(y))
    return y.astype(np.float32)
