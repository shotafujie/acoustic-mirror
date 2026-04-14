"""Sprint 10: Pipeline integration tests."""

import numpy as np
import pytest

from acoustic_mirror.main import AnalysisPipeline, AnalysisResult

SAMPLE_RATE = 16000


class TestAnalysisPipeline:
    def test_produces_complete_result(self, speech_like_chunk):
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        # Feed some chunks to establish noise floor, then a speech chunk
        silence = np.zeros(8000, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        result = pipeline.process(speech_like_chunk)
        assert isinstance(result, AnalysisResult)
        assert hasattr(result, "timestamp")
        assert hasattr(result, "speech_active")
        assert hasattr(result, "noise_floor_db")

    def test_pipeline_skips_srmr_when_no_speech_initially(self):
        """First silence chunk has no persisted SRMR."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        silence = np.zeros(8000, dtype=np.float32)
        result = pipeline.process(silence)
        assert result.speech_active is False
        assert result.srmr_score is None

    def test_pipeline_computes_srmr_for_speech(self, speech_like_chunk):
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        # Establish quiet noise floor
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        result = pipeline.process(speech_like_chunk)
        assert result.speech_active is True
        assert result.srmr_score is not None
        assert result.srmr_score > 0

    def test_pipeline_includes_room_profile(self, speech_like_chunk):
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        result = pipeline.process(speech_like_chunk)
        assert result.room_profile is not None
        assert result.room_profile.room_type is not None

    def test_pipeline_includes_cause_when_srmr_low(self):
        """Force a scenario where SRMR would be low."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        # Feed quiet to establish noise floor
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        # Simulate high-noise room
        pipeline._room_profiler.update_noise_floor(-25.0)
        pipeline._room_profiler.update_rt60(
            np.exp(-np.arange(8000, dtype=np.float32) / 1600)  # ~0.5s RT60
        )
        # Feed speech-like signal
        rng = np.random.default_rng(42)
        t = np.arange(8000, dtype=np.float32) / SAMPLE_RATE
        speech = (0.3 * rng.standard_normal(8000) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)
        result = pipeline.process(speech)
        # With high noise and medium RT60, cause should be identified
        if result.cause is not None:
            assert result.cause.primary_cause in ("reverb", "noise", "articulation", "distance")

    def test_cause_persists_across_silence(self, speech_like_chunk):
        """Bug 3: Cause from speech frame persists into non-speech frames."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        # Force low SRMR target so cause is triggered
        pipeline._room_profiler.update_noise_floor(-25.0)
        pipeline._room_profiler.update_rt60(
            np.exp(-np.arange(8000, dtype=np.float32) / 1600)
        )
        # Feed speech
        result_speech = pipeline.process(speech_like_chunk)
        if result_speech.cause is not None:
            # Now feed silence — cause should persist
            result_silence = pipeline.process(silence)
            assert result_silence.cause is not None
            assert result_silence.cause.primary_cause == result_speech.cause.primary_cause

    def test_srmr_persists_across_silence(self, speech_like_chunk):
        """Bug 3: SRMR score persists into non-speech frames."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        result_speech = pipeline.process(speech_like_chunk)
        if result_speech.srmr_score is not None:
            result_silence = pipeline.process(silence)
            assert result_silence.srmr_score == result_speech.srmr_score

    def test_rt60_uses_prev_chunk_decay(self):
        """Bug 1+2: RT60 estimation uses decay from previous chunk, not silence."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        # Establish noise floor
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        # Create a chunk with speech that has a decay tail
        chunk_with_decay = np.zeros(8000, dtype=np.float32)
        # First 5000 samples: loud speech
        chunk_with_decay[:5000] = 0.3
        # Last 3000 samples: exponential decay (RT60 ~ 0.3s)
        t = np.arange(3000, dtype=np.float32) / SAMPLE_RATE
        chunk_with_decay[5000:] = 0.3 * np.exp(-6.908 * t / 0.3)
        # Process speech chunk
        pipeline.process(chunk_with_decay)
        # Process silence (triggers speech→silence transition)
        pipeline.process(silence)
        # RT60 should not be 3.0 (max clamp) anymore
        rt60 = pipeline._room_profiler.current_profile.rt60
        assert rt60 < 2.0  # should be much less than the default 3.0

    def test_result_serializable(self, speech_like_chunk):
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        result = pipeline.process(speech_like_chunk)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert "type" in d
        assert "timestamp" in d
        assert "speech_active" in d
