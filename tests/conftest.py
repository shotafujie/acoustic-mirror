"""Shared test fixtures — synthetic audio signals for deterministic testing."""

import numpy as np
import pytest

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 8000  # 500ms at 16kHz


@pytest.fixture
def sample_rate():
    return SAMPLE_RATE


@pytest.fixture
def silence_chunk():
    """500ms of silence."""
    return np.zeros(CHUNK_SAMPLES, dtype=np.float32)


@pytest.fixture
def sine_chunk():
    """500ms sine wave at 440Hz, amplitude 0.5."""
    t = np.arange(CHUNK_SAMPLES, dtype=np.float32) / SAMPLE_RATE
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def speech_like_chunk():
    """Amplitude-modulated noise simulating speech temporal envelope.

    White noise modulated at 4Hz (syllable rate) to mimic the temporal
    structure of natural speech.
    """
    rng = np.random.default_rng(42)
    t = np.arange(CHUNK_SAMPLES, dtype=np.float32) / SAMPLE_RATE
    noise = rng.standard_normal(CHUNK_SAMPLES).astype(np.float32)
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 4 * t))  # 4Hz modulation
    return (0.3 * noise * envelope).astype(np.float32)


@pytest.fixture
def reverberant_chunk(speech_like_chunk):
    """Speech-like signal convolved with synthetic exponential impulse response.

    RT60 ~ 0.8s (long reverb tail).
    """
    rt60 = 0.8
    ir_length = int(rt60 * SAMPLE_RATE)
    t_ir = np.arange(ir_length, dtype=np.float32) / SAMPLE_RATE
    ir = np.exp(-6.908 * t_ir / rt60).astype(np.float32)  # 6.908 = ln(1000)
    ir /= np.sqrt(np.sum(ir**2))  # normalize energy
    convolved = np.convolve(speech_like_chunk, ir, mode="full")[:CHUNK_SAMPLES]
    return convolved.astype(np.float32)


@pytest.fixture
def noisy_chunk(speech_like_chunk):
    """Speech-like signal with additive white noise at 0dB SNR."""
    rng = np.random.default_rng(123)
    noise = rng.standard_normal(CHUNK_SAMPLES).astype(np.float32)
    signal_power = np.mean(speech_like_chunk**2)
    noise_power = np.mean(noise**2)
    noise_scaled = noise * np.sqrt(signal_power / noise_power)  # 0dB SNR
    return (speech_like_chunk + noise_scaled).astype(np.float32)
