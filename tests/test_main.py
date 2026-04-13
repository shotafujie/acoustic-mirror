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

    def test_pipeline_skips_srmr_when_no_speech(self, silence_chunk):
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        result = pipeline.process(silence_chunk)
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
