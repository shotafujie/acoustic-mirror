"""Sprint 5: Cause separator tests."""

import pytest

from acoustic_mirror.analysis.cause_separator import CauseResult, CauseSeparator
from acoustic_mirror.analysis.room_profiler import RoomProfile, RoomType


def _profile(rt60=0.2, noise=-50.0, drr=10.0) -> RoomProfile:
    """Helper to create a RoomProfile with overridable defaults."""
    room_type = RoomType.QUIET_SMALL
    return RoomProfile(
        rt60=rt60,
        noise_floor_db=noise,
        early_to_late_ratio_db=drr,
        room_type=room_type,
        srmr_target=room_type.srmr_target,
    )


class TestCauseDiagnosis:
    def test_no_cause_when_srmr_above_target(self):
        sep = CauseSeparator()
        profile = _profile()
        result = sep.diagnose(srmr_score=6.0, srmr_target=5.0, room_profile=profile)
        assert result.primary_cause is None

    def test_high_rt60_blames_reverb(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.8, noise=-50.0, drr=10.0)
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert result.primary_cause == "reverb"

    def test_high_noise_blames_noise(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.1, noise=-20.0, drr=10.0)
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert result.primary_cause == "noise"

    def test_low_drr_blames_distance(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.1, noise=-50.0, drr=-2.0)
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert result.primary_cause == "distance"

    def test_residual_blames_articulation(self):
        """When room metrics are fine but SRMR is still low."""
        sep = CauseSeparator()
        profile = _profile(rt60=0.15, noise=-55.0, drr=12.0)
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert result.primary_cause == "articulation"

    def test_cause_includes_action_text(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.8)
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert result.action != ""
        assert isinstance(result.action, str)

    def test_returns_cause_result_dataclass(self):
        sep = CauseSeparator()
        profile = _profile()
        result = sep.diagnose(srmr_score=2.0, srmr_target=5.0, room_profile=profile)
        assert isinstance(result, CauseResult)
        assert hasattr(result, "primary_cause")
        assert hasattr(result, "severity")
        assert hasattr(result, "action")
        assert hasattr(result, "scores")


class TestCauseScoring:
    def test_reverb_score_proportional_to_rt60(self):
        sep = CauseSeparator()
        p_low = _profile(rt60=0.2)
        p_high = _profile(rt60=0.9)
        r_low = sep.diagnose(2.0, 5.0, p_low)
        r_high = sep.diagnose(2.0, 5.0, p_high)
        assert r_high.scores["reverb"] > r_low.scores["reverb"]

    def test_noise_score_proportional_to_noise_floor(self):
        sep = CauseSeparator()
        p_low = _profile(noise=-55.0)
        p_high = _profile(noise=-20.0)
        r_low = sep.diagnose(2.0, 5.0, p_low)
        r_high = sep.diagnose(2.0, 5.0, p_high)
        assert r_high.scores["noise"] > r_low.scores["noise"]

    def test_distance_score_inversely_proportional_to_drr(self):
        sep = CauseSeparator()
        p_close = _profile(drr=15.0)
        p_far = _profile(drr=-3.0)
        r_close = sep.diagnose(2.0, 5.0, p_close)
        r_far = sep.diagnose(2.0, 5.0, p_far)
        assert r_far.scores["distance"] > r_close.scores["distance"]


class TestCauseActions:
    def test_reverb_action_in_japanese(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.8)
        result = sep.diagnose(2.0, 5.0, profile)
        assert "ゆっくり" in result.action

    def test_noise_action_in_japanese(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.1, noise=-20.0, drr=10.0)
        result = sep.diagnose(2.0, 5.0, profile)
        assert "大きく" in result.action or "声" in result.action

    def test_distance_action_in_japanese(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.1, noise=-50.0, drr=-2.0)
        result = sep.diagnose(2.0, 5.0, profile)
        assert "近" in result.action

    def test_articulation_action_in_japanese(self):
        sep = CauseSeparator()
        profile = _profile(rt60=0.15, noise=-55.0, drr=12.0)
        result = sep.diagnose(2.0, 5.0, profile)
        assert "はっきり" in result.action


class TestSeveritySuppression:
    def test_low_severity_suppressed(self):
        """When SRMR is only slightly below target, severity should be low."""
        sep = CauseSeparator()
        profile = _profile(rt60=0.35)
        # Just barely below target
        result = sep.diagnose(srmr_score=4.8, srmr_target=5.0, room_profile=profile)
        assert result.severity < 0.3
