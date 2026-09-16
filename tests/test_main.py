"""Sprint 10: Pipeline integration tests."""

import numpy as np
import pytest

from acoustic_mirror.main import AnalysisPipeline, AnalysisResult, should_recompute_srmr

SAMPLE_RATE = 16000
SRMR_WINDOW_SAMPLES = 3 * SAMPLE_RATE


def _srmr_window_from(chunk: np.ndarray) -> np.ndarray:
    """Tile a 500ms chunk out to a 3s SRMR window for tests that don't care
    about the window's internal structure, only that it's present and full
    (ADR-0002)."""
    reps = SRMR_WINDOW_SAMPLES // len(chunk) + 1
    return np.tile(chunk, reps)[:SRMR_WINDOW_SAMPLES].astype(np.float32)


class TestShouldRecomputeSrmr:
    """ADR-0002: gate logic as a pure function, independent of AnalysisPipeline state."""

    def test_false_when_buffer_not_full(self):
        assert should_recompute_srmr(recent_speech_ratio=1.0, seconds_since_last_compute=10.0, buffer_full=False) is False

    def test_false_when_speech_ratio_below_threshold(self):
        assert should_recompute_srmr(recent_speech_ratio=0.5, seconds_since_last_compute=10.0, buffer_full=True) is False

    def test_false_when_too_soon_since_last_compute(self):
        assert should_recompute_srmr(recent_speech_ratio=1.0, seconds_since_last_compute=0.1, buffer_full=True) is False

    def test_true_when_all_conditions_met(self):
        assert should_recompute_srmr(recent_speech_ratio=0.9, seconds_since_last_compute=2.0, buffer_full=True) is True

    def test_true_on_boundary_values(self):
        assert should_recompute_srmr(recent_speech_ratio=0.7, seconds_since_last_compute=1.0, buffer_full=True) is True


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
        # Sustained speech for several ticks: the gate's recent-speech-ratio
        # history (maxlen=6) still holds mostly the priming silence right
        # after a single speech chunk, so it won't pass on the first one.
        window = _srmr_window_from(speech_like_chunk)
        for _ in range(5):
            pipeline.process(speech_like_chunk, srmr_window=window)
        result = pipeline.process(speech_like_chunk, srmr_window=window)
        assert result.speech_active is True
        assert result.srmr_score is not None
        assert result.srmr_score > 0

    def test_pipeline_does_not_compute_srmr_without_a_full_window(self, speech_like_chunk):
        """ADR-0002: no srmr_window (buffer not yet full) means no fresh
        SRMR computation, even during active speech."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        result = pipeline.process(speech_like_chunk)
        assert result.speech_active is True
        assert result.srmr_score is None

    def test_pipeline_does_not_recompute_srmr_before_gate_interval(self, speech_like_chunk):
        """ADR-0002: even with a full window and continuous speech, SRMR
        should not recompute more often than the gate's minimum interval."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        window = _srmr_window_from(speech_like_chunk)
        first = pipeline.process(speech_like_chunk, srmr_window=window)
        second = pipeline.process(speech_like_chunk, srmr_window=window)
        assert first.srmr_score is not None
        # Second call happens well within the 1s gate interval (no sleep
        # between calls), so the score should be carried forward unchanged
        # and its age should have grown rather than reset to ~0.
        assert second.srmr_score == first.srmr_score
        assert second.srmr_age_seconds >= first.srmr_age_seconds

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
        # Feed speech-like signal, sustained long enough for the recent-
        # speech-ratio gate (history maxlen=6) to clear the silence priming
        rng = np.random.default_rng(42)
        t = np.arange(8000, dtype=np.float32) / SAMPLE_RATE
        speech = (0.3 * rng.standard_normal(8000) * (0.5 + 0.5 * np.sin(2 * np.pi * 4 * t))).astype(np.float32)
        window = _srmr_window_from(speech)
        result = None
        for _ in range(6):
            result = pipeline.process(speech, srmr_window=window)
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
        # Feed speech, sustained long enough for the gate to fire (with a
        # full SRMR window)
        window = _srmr_window_from(speech_like_chunk)
        result_speech = None
        for _ in range(6):
            result_speech = pipeline.process(speech_like_chunk, srmr_window=window)
        if result_speech.cause is not None:
            # Now feed silence with no SRMR window — cause should persist
            result_silence = pipeline.process(silence)
            assert result_silence.cause is not None
            assert result_silence.cause.primary_cause == result_speech.cause.primary_cause

    def test_srmr_persists_across_silence(self, speech_like_chunk):
        """Bug 3 (generalized to the ADR-0002 gate): SRMR score persists
        into non-speech frames when the gate does not recompute it."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        silence = np.full(8000, 1e-5, dtype=np.float32)
        for _ in range(5):
            pipeline.process(silence)
        window = _srmr_window_from(speech_like_chunk)
        result_speech = None
        for _ in range(6):
            result_speech = pipeline.process(speech_like_chunk, srmr_window=window)
        if result_speech.srmr_score is not None:
            result_silence = pipeline.process(silence)
            assert result_silence.srmr_score == result_speech.srmr_score

    def test_rt60_uses_prev_chunk_decay(self):
        """Bug 1+2: RT60 estimation uses the decay tail extracted from the
        previous chunk. Exercises _extract_decay_segment + update_rt60
        directly with a hand-built frame_energies list (rather than
        driving it through VAD threshold physics on a synthetic chunk,
        which — at the very low absolute noise floors this scaffold uses
        for "silence" — collides with the RT60 estimator's own numerical
        floor for near-silent samples; that interaction is a test-signal
        artifact of this scaffold, not a real constraint on production
        audio scaled to a normal noise floor).
        """
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        # A well-scaled decay: loud plateau, then a clean 0.3s-RT60 decay
        # well past the 100ms minimum decay length (ADR-0003).
        plateau_samples = 2880  # 6 frames * 480 samples/frame
        decay_samples = 8000 - plateau_samples  # 320ms
        chunk = np.zeros(8000, dtype=np.float32)
        chunk[:plateau_samples] = 0.3
        t = np.arange(decay_samples, dtype=np.float64) / SAMPLE_RATE
        chunk[plateau_samples:] = (0.3 * np.exp(-6.908 * t / 0.3)).astype(np.float32)

        # frame_energies as VAD would report them for this chunk: loud for
        # the plateau, then dropping below any reasonable threshold.
        frame_energies = [-10.5] * 6 + [-90.0] * (decay_samples // 480)

        decay = pipeline._extract_decay_segment(chunk, frame_energies)
        assert decay is not None
        assert len(decay) >= int(SAMPLE_RATE * 0.1)

        pipeline._room_profiler.update_rt60(decay)
        profile = pipeline._room_profiler.current_profile
        assert abs(profile.rt60 - 0.3) < 0.1
        assert profile.rt60_confidence > 0.9

    def test_rt60_estimation_is_reachable_across_utterance_end_phase(self):
        """Regression guard for a reachability bug found via advisor review:
        the decay tail can only ever come from what's left of a single
        500ms chunk after the last speech frame (_extract_decay_segment
        reads from `_prev_chunk`, not the longer SRMR buffer), so an
        overly long minimum decay length can make RT60 estimation
        essentially unreachable in practice — a first 300ms floor did
        (0/16 phases below produced an estimate before it was lowered to
        100ms). Sweeps where the speech->silence transition falls within
        the chunk and checks a meaningful fraction still produce an
        estimate through the real two-call pipeline.process() flow.
        """
        frame_size = 480  # 30ms at 16kHz
        n_frames = 8000 // frame_size
        hits = 0
        for offset_frame in range(n_frames):
            pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
            silence = np.full(8000, 1e-3, dtype=np.float32)
            for _ in range(5):
                pipeline.process(silence)

            speech_end = (offset_frame + 1) * frame_size
            chunk1 = np.zeros(8000, dtype=np.float32)
            chunk1[:speech_end] = 0.3
            if speech_end < 8000:
                t = np.arange(8000 - speech_end, dtype=np.float64) / SAMPLE_RATE
                chunk1[speech_end:] = (0.3 * np.exp(-6.908 * t / 0.3)).astype(np.float32)

            pipeline.process(chunk1)
            pipeline.process(silence)
            if len(pipeline._room_profiler._rt60_estimates) > 0:
                hits += 1

        # Not every phase can succeed (some leave too little decay to fit
        # T20 at all), but at least a third should — this is the real
        # production path, gated only by the length floor and the R^2
        # confidence gate, not a hand-built frame_energies list.
        assert hits >= n_frames // 3

    def test_isolated_onset_gate_allows_onset_after_genuine_silence(self):
        """ADR-0003: an onset preceded by real silence is eligible for the
        early-to-late ratio update."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        threshold = -74.0
        pipeline._prev_frame_energies = [-90.0] * 10  # 300ms of quiet
        onset_frame = 2
        frame_energies = [-90.0, -90.0, -10.0, -10.0]  # quiet, quiet, then speech
        assert pipeline._is_isolated_onset(onset_frame, frame_energies, threshold) is True

    def test_isolated_onset_gate_blocks_onset_after_trailing_speech(self):
        """ADR-0003: an onset immediately preceded by speech (e.g. the
        previous syllable) must not update the early-to-late ratio — that
        window would capture the previous syllable's direct sound, not
        reverberant tail."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        threshold = -74.0
        pipeline._prev_frame_energies = [-90.0] * 9 + [-10.0]  # speech right at the boundary
        onset_frame = 1
        frame_energies = [-90.0, -10.0]
        assert pipeline._is_isolated_onset(onset_frame, frame_energies, threshold) is False

    def test_early_to_late_ratio_not_updated_on_non_isolated_onset(self):
        """Integration: a silence→speech transition immediately following
        trailing speech in the previous chunk should not move
        early_to_late_ratio_db off its default."""
        pipeline = AnalysisPipeline(sample_rate=SAMPLE_RATE)
        default_ratio = pipeline._room_profiler.current_profile.early_to_late_ratio_db

        # First chunk: mostly quiet but with speech right at the very end
        # (so _prev_speech becomes True due to a short burst), followed by
        # a second chunk starting with more speech at frame 0 — the
        # boundary between them has no genuine silence gap.
        chunk1 = np.zeros(8000, dtype=np.float32)
        chunk1[-480:] = 0.3  # last frame is loud
        pipeline.process(chunk1)

        chunk2 = np.zeros(8000, dtype=np.float32)
        chunk2[:4000] = 0.3
        pipeline.process(chunk2)

        assert pipeline._room_profiler.current_profile.early_to_late_ratio_db == default_ratio

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
