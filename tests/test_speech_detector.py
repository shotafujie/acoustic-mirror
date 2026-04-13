"""Sprint 2: Speech detector (energy-based VAD) tests."""

import numpy as np
import pytest

from acoustic_mirror.analysis.speech_detector import (
    SpeechDetector,
    frame_energy_db,
)

SAMPLE_RATE = 16000


class TestFrameEnergy:
    def test_silence_energy_is_very_low(self):
        frame = np.zeros(480, dtype=np.float32)
        assert frame_energy_db(frame) < -80

    def test_known_amplitude_energy(self):
        """Constant amplitude A => energy = A^2 => dB = 10*log10(A^2)."""
        a = 0.5
        frame = np.full(480, a, dtype=np.float32)
        expected_db = 10 * np.log10(a**2)
        assert abs(frame_energy_db(frame) - expected_db) < 0.1

    def test_sine_wave_energy(self):
        """Sine amplitude 1.0 => RMS energy = 0.5 => dB ~ -3.01."""
        t = np.arange(480, dtype=np.float32) / SAMPLE_RATE
        frame = np.sin(2 * np.pi * 440 * t).astype(np.float32)
        assert abs(frame_energy_db(frame) - (-3.01)) < 0.5


class TestSpeechDetector:
    def test_silence_classified_as_non_speech(self, silence_chunk):
        det = SpeechDetector(sample_rate=SAMPLE_RATE)
        # Feed some silence to establish noise floor
        for _ in range(5):
            det.process(silence_chunk)
        result = det.process(silence_chunk)
        assert result.is_speech is False

    def test_loud_signal_classified_as_speech(self, silence_chunk):
        det = SpeechDetector(sample_rate=SAMPLE_RATE)
        # Establish noise floor with silence
        for _ in range(5):
            det.process(silence_chunk)
        # Now feed a loud signal
        loud = np.full(8000, 0.3, dtype=np.float32)
        result = det.process(loud)
        assert result.is_speech is True

    def test_speech_ratio_for_mixed_signal(self):
        det = SpeechDetector(sample_rate=SAMPLE_RATE)
        # Establish low noise floor
        quiet = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            det.process(quiet)
        # Create chunk with first half loud, second half silence
        mixed = np.zeros(8000, dtype=np.float32)
        mixed[:4000] = 0.3
        result = det.process(mixed)
        # About half the frames should be speech
        assert 0.3 < result.speech_ratio < 0.7

    def test_30ms_frame_size(self):
        det = SpeechDetector(sample_rate=SAMPLE_RATE, frame_ms=30)
        # Establish quiet noise floor first
        quiet = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            det.process(quiet)
        # 30ms at 16kHz = 480 samples; 500ms chunk = 16.67 frames => 16 full frames
        chunk = np.ones(8000, dtype=np.float32)
        result = det.process(chunk)
        # Should work without error; speech_ratio should be 1.0
        assert result.speech_ratio == pytest.approx(1.0, abs=0.1)

    def test_noise_floor_adapts(self):
        det = SpeechDetector(sample_rate=SAMPLE_RATE)
        # Feed quiet signal
        quiet = np.full(8000, 1e-4, dtype=np.float32)
        for _ in range(10):
            det.process(quiet)
        floor1 = det.process(quiet).noise_floor_db
        # Feed louder background
        louder = np.full(8000, 1e-2, dtype=np.float32)
        for _ in range(20):
            det.process(louder)
        floor2 = det.process(louder).noise_floor_db
        assert floor2 > floor1

    def test_result_has_all_fields(self, silence_chunk):
        det = SpeechDetector(sample_rate=SAMPLE_RATE)
        result = det.process(silence_chunk)
        assert hasattr(result, "is_speech")
        assert hasattr(result, "speech_ratio")
        assert hasattr(result, "noise_floor_db")
        assert hasattr(result, "energy_db")
