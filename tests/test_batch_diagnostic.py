"""Batch diagnostic mode: whole-clip, multi-event analysis (docs/adr/ADR-0004)."""

import numpy as np
import pytest
from scipy.signal import resample_poly

from acoustic_mirror.analysis.batch_diagnostic import (
    MIN_DURATION_SECONDS,
    DiagnosticResult,
    diagnose,
    find_decay_events,
)
from tests.synth import SAMPLE_RATE, reverberant_utterances, synth_utterances


class TestFindDecayEvents:
    def test_one_event_per_utterance_in_clean_signal(self):
        y = reverberant_utterances(rt60=0.3, seed=1)
        events = find_decay_events(y, SAMPLE_RATE)
        # 7s of 0.3s bursts + ~0.7s gaps -> about 7 utterances
        assert 5 <= len(events) <= 9

    def test_event_starts_after_burst_plateau(self):
        """Origin is where the decay actually begins, not the burst's first
        loud frame (ADR-0004: skip the source's flat plateau)."""
        y = reverberant_utterances(rt60=0.3, seed=1)
        start, _ = find_decay_events(y, SAMPLE_RATE)[0]
        # first burst spans 0.2s-0.5s
        assert 0.4 * SAMPLE_RATE <= start <= 0.55 * SAMPLE_RATE

    def test_event_ends_before_next_utterance(self):
        y = reverberant_utterances(rt60=1.5, gap=0.7, seed=1)
        events = find_decay_events(y, SAMPLE_RATE)
        for (_, end), (next_start, _) in zip(events, events[1:]):
            assert end <= next_start

    def test_no_events_in_silence(self):
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(7 * SAMPLE_RATE)).astype(np.float32)
        assert find_decay_events(y, SAMPLE_RATE) == []


class TestRT60Validity:
    """ADR-0004 acceptance criterion: ±15% of true RT60."""

    @pytest.mark.parametrize("rt60", [0.3, 0.6, 1.0])
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_within_15_percent_with_normal_pauses(self, rt60, seed):
        result = diagnose(reverberant_utterances(rt60, gap=0.7, seed=seed), SAMPLE_RATE)
        assert result.rt60 is not None
        assert abs(result.rt60 - rt60) / rt60 <= 0.15

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_long_rt60_within_15_percent_with_long_pauses(self, seed):
        result = diagnose(reverberant_utterances(1.5, gap=1.2, seed=seed), SAMPLE_RATE)
        assert result.rt60 is not None
        assert abs(result.rt60 - 1.5) / 1.5 <= 0.15

    def test_long_rt60_short_pauses_is_known_underestimate(self):
        """Known limit (ADR-0004): 0.7s pauses cut a 1.5s tail before -25dB,
        so the estimate comes out ~20% short. Pinned so a change in this
        behavior is noticed, not to endorse it."""
        result = diagnose(reverberant_utterances(1.5, gap=0.7, seed=1), SAMPLE_RATE)
        assert result.rt60 is not None
        assert 1.05 <= result.rt60 < 1.5 * 0.85

    def test_reports_accepted_event_values(self):
        result = diagnose(reverberant_utterances(0.6, seed=1), SAMPLE_RATE)
        assert len(result.rt60_events) >= 3
        assert result.rt60 == pytest.approx(np.percentile(result.rt60_events, 70))
        assert result.rt60_rejected_count >= 0

    def test_fewer_than_three_events_gives_no_rt60(self):
        y = reverberant_utterances(0.6, seed=1)[: int(1.2 * SAMPLE_RATE)]
        y = np.concatenate([y, np.zeros(2 * SAMPLE_RATE, dtype=np.float32) + 1e-3])
        result = diagnose(y, SAMPLE_RATE)
        assert result.rt60 is None
        assert "rt60" in result.defaulted_metrics


class TestResampling:
    def test_48k_input_matches_16k_estimate(self):
        y16 = reverberant_utterances(0.6, seed=1)
        y48 = resample_poly(y16, 3, 1).astype(np.float32)
        r16 = diagnose(y16, SAMPLE_RATE)
        r48 = diagnose(y48, 48000)
        assert r48.rt60 == pytest.approx(r16.rt60, rel=0.1)
        assert r48.duration_seconds == pytest.approx(r16.duration_seconds, abs=0.01)


class TestInputValidation:
    def test_rejects_clip_shorter_than_minimum(self):
        with pytest.raises(ValueError):
            diagnose(np.zeros(int((MIN_DURATION_SECONDS - 0.1) * SAMPLE_RATE), dtype=np.float32), SAMPLE_RATE)


class TestEarlyToLateRatio:
    def test_estimated_from_isolated_onsets(self):
        result = diagnose(reverberant_utterances(0.3, gap=0.7, seed=1), SAMPLE_RATE)
        assert result.early_to_late_event_count >= 1
        assert result.early_to_late_ratio_db is not None

    def test_none_without_isolated_onsets(self):
        # continuous bursts, no pauses: no onset is preceded by 200ms silence
        y = synth_utterances(gap=0.0, seed=1)
        y = y + 1e-3 * np.random.default_rng(0).standard_normal(len(y)).astype(np.float32)
        result = diagnose(y, SAMPLE_RATE)
        assert result.early_to_late_ratio_db is None
        assert "early_to_late_ratio" in result.defaulted_metrics


class TestSRMRAndRoom:
    def test_srmr_computed_on_speechy_clip(self):
        result = diagnose(reverberant_utterances(0.3, gap=0.2, seed=1), SAMPLE_RATE)
        assert result.srmr_score is not None

    def test_srmr_skipped_when_mostly_silent(self):
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(5 * SAMPLE_RATE)).astype(np.float32)
        result = diagnose(y, SAMPLE_RATE)
        assert result.srmr_score is None

    def test_room_classified_from_estimated_rt60(self):
        result = diagnose(reverberant_utterances(1.0, gap=1.2, seed=1), SAMPLE_RATE)
        assert result.room_profile.room_type.value.startswith("reverberant")
        assert result.room_profile.rt60 == pytest.approx(result.rt60)

    def test_room_uses_default_rt60_when_undetermined(self):
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(5 * SAMPLE_RATE)).astype(np.float32)
        result = diagnose(y, SAMPLE_RATE)
        assert result.room_profile.rt60 == pytest.approx(0.2)
        assert "rt60" in result.defaulted_metrics


class TestToDict:
    def test_serializable_shape(self):
        import json

        result = diagnose(reverberant_utterances(0.6, seed=1), SAMPLE_RATE)
        assert isinstance(result, DiagnosticResult)
        d = result.to_dict()
        json.dumps(d)  # must be JSON-serializable
        assert d["type"] == "diagnostic"
        assert set(d["rt60"]) >= {"value", "events", "rejected_count"}
        assert set(d["early_to_late_ratio"]) >= {"value_db", "event_count"}
        assert "room_profile" in d and "defaulted_metrics" in d

    def test_undetermined_metrics_serialize_as_null(self):
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(5 * SAMPLE_RATE)).astype(np.float32)
        d = diagnose(y, SAMPLE_RATE).to_dict()
        assert d["rt60"]["value"] is None
        assert d["srmr_score"] is None
