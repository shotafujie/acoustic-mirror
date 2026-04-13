"""Sprint 4: SRMR computation tests."""

import numpy as np
import pytest

from acoustic_mirror.analysis.srmr import (
    GammatoneFilterbank,
    SRMRProcessor,
    compute_modulation_energy,
)

SAMPLE_RATE = 16000


class TestGammatoneFilterbank:
    def test_23_channels_created(self):
        fb = GammatoneFilterbank(n_filters=23, sample_rate=SAMPLE_RATE)
        assert fb.n_filters == 23

    def test_center_frequencies_are_increasing(self):
        fb = GammatoneFilterbank(n_filters=23, sample_rate=SAMPLE_RATE)
        cfs = fb.center_frequencies
        assert all(cfs[i] < cfs[i + 1] for i in range(len(cfs) - 1))

    def test_center_frequencies_span_correct_range(self):
        fb = GammatoneFilterbank(
            n_filters=23, low_freq=125, high_freq=8000, sample_rate=SAMPLE_RATE
        )
        assert fb.center_frequencies[0] >= 100  # near 125Hz
        assert fb.center_frequencies[-1] <= 8000

    def test_filterbank_output_shape(self):
        fb = GammatoneFilterbank(n_filters=23, sample_rate=SAMPLE_RATE)
        signal = np.random.default_rng(42).standard_normal(8000).astype(np.float32)
        output = fb.apply(signal)
        assert output.shape == (23, 8000)

    def test_pure_tone_activates_correct_channel(self):
        fb = GammatoneFilterbank(n_filters=23, sample_rate=SAMPLE_RATE)
        t = np.arange(8000, dtype=np.float32) / SAMPLE_RATE
        tone_1k = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
        output = fb.apply(tone_1k)
        channel_energies = np.sum(output**2, axis=1)
        peak_channel = np.argmax(channel_energies)
        # The peak channel's center frequency should be near 1000Hz
        assert abs(fb.center_frequencies[peak_channel] - 1000) < 300

    def test_silence_produces_near_zero_output(self):
        fb = GammatoneFilterbank(n_filters=23, sample_rate=SAMPLE_RATE)
        silence = np.zeros(8000, dtype=np.float32)
        output = fb.apply(silence)
        assert np.max(np.abs(output)) < 1e-6


class TestModulationEnergy:
    def test_output_shape(self):
        """Modulation energy matrix should be (n_channels, n_mod_bands)."""
        rng = np.random.default_rng(42)
        envelopes = np.abs(rng.standard_normal((23, 8000))).astype(np.float32)
        energy = compute_modulation_energy(envelopes, SAMPLE_RATE)
        assert energy.shape[0] == 23
        assert energy.shape[1] == 8  # 8 modulation bands

    def test_energy_is_non_negative(self):
        rng = np.random.default_rng(42)
        envelopes = np.abs(rng.standard_normal((23, 8000))).astype(np.float32)
        energy = compute_modulation_energy(envelopes, SAMPLE_RATE)
        assert np.all(energy >= 0)


class TestSRMR:
    def test_clean_speech_srmr_is_high(self, speech_like_chunk):
        proc = SRMRProcessor(sample_rate=SAMPLE_RATE)
        result = proc.process(speech_like_chunk, is_speech=True)
        assert result.is_valid
        # Clean speech-like signal should have moderate-to-high SRMR
        assert result.srmr_score > 1.0

    def test_reverberant_srmr_is_lower(self, speech_like_chunk):
        """Adding heavy reverb should reduce SRMR (more high-mod energy)."""
        proc1 = SRMRProcessor(sample_rate=SAMPLE_RATE)
        clean_result = proc1.process(speech_like_chunk, is_speech=True)

        # Create a heavily reverberant version with a long, dense IR
        rng = np.random.default_rng(99)
        rt60 = 1.5
        ir_len = int(rt60 * SAMPLE_RATE)
        t_ir = np.arange(ir_len, dtype=np.float64) / SAMPLE_RATE
        # Exponential decay envelope with noise to simulate diffuse reflections
        ir = rng.standard_normal(ir_len) * np.exp(-6.908 * t_ir / rt60)
        ir = ir.astype(np.float32)
        # Normalize IR to unit energy
        ir /= np.sqrt(np.sum(ir**2))

        reverbed = np.convolve(speech_like_chunk, ir, mode="full")[: len(speech_like_chunk)]
        # Match RMS so level difference doesn't confound the comparison
        rms_clean = np.sqrt(np.mean(speech_like_chunk**2))
        rms_reverb = np.sqrt(np.mean(reverbed**2))
        if rms_reverb > 0:
            reverbed = reverbed * (rms_clean / rms_reverb)

        proc2 = SRMRProcessor(sample_rate=SAMPLE_RATE)
        reverb_result = proc2.process(reverbed.astype(np.float32), is_speech=True)
        assert reverb_result.srmr_score < clean_result.srmr_score

    def test_silence_returns_invalid(self, silence_chunk):
        proc = SRMRProcessor(sample_rate=SAMPLE_RATE)
        result = proc.process(silence_chunk, is_speech=False)
        assert result.is_valid is False

    def test_srmr_result_has_fields(self, speech_like_chunk):
        proc = SRMRProcessor(sample_rate=SAMPLE_RATE)
        result = proc.process(speech_like_chunk, is_speech=True)
        assert hasattr(result, "srmr_score")
        assert hasattr(result, "energy")
        assert hasattr(result, "is_valid")

    def test_srmr_is_positive_for_speech(self, speech_like_chunk):
        proc = SRMRProcessor(sample_rate=SAMPLE_RATE)
        result = proc.process(speech_like_chunk, is_speech=True)
        assert result.srmr_score > 0

    def test_energy_matrix_shape(self, speech_like_chunk):
        proc = SRMRProcessor(sample_rate=SAMPLE_RATE)
        result = proc.process(speech_like_chunk, is_speech=True)
        assert result.energy.shape == (23, 8)
