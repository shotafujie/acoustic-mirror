"""Sprint 6: Haptic pattern definition tests."""

import pytest

from acoustic_mirror.feedback.haptic_patterns import (
    PATTERNS,
    HapticPattern,
    get_pattern,
)


class TestHapticPattern:
    def test_pattern_has_required_fields(self):
        p = list(PATTERNS.values())[0]
        assert hasattr(p, "name")
        assert hasattr(p, "cause")
        assert hasattr(p, "sequence")
        assert hasattr(p, "description")

    def test_vibration_sequence_is_list_of_tuples(self):
        for p in PATTERNS.values():
            assert isinstance(p.sequence, list)
            for item in p.sequence:
                assert len(item) == 2  # (intensity, duration_ms)

    def test_intensity_range_0_to_1(self):
        for p in PATTERNS.values():
            for intensity, _ in p.sequence:
                assert 0.0 <= intensity <= 1.0

    def test_duration_ms_property(self):
        for p in PATTERNS.values():
            total = sum(d for _, d in p.sequence)
            assert p.duration_ms == total


class TestPatternRegistry:
    def test_has_pattern_for_each_cause(self):
        for cause in ("reverb", "noise", "articulation", "distance"):
            assert cause in PATTERNS

    def test_get_pattern_by_cause(self):
        p = get_pattern("reverb")
        assert isinstance(p, HapticPattern)
        assert p.cause == "reverb"

    def test_get_pattern_unknown_raises(self):
        with pytest.raises(KeyError):
            get_pattern("unknown")


class TestPatternSerialization:
    def test_pattern_to_dict(self):
        p = get_pattern("reverb")
        d = p.to_dict()
        assert "name" in d
        assert "cause" in d
        assert "sequence" in d
        assert "duration_ms" in d

    def test_bar_chart_data(self):
        p = get_pattern("noise")
        bars = p.bar_chart_data()
        assert isinstance(bars, list)
        for bar in bars:
            assert "intensity" in bar
            assert "duration_ms" in bar
            assert "offset_ms" in bar
        # Offsets should be cumulative
        if len(bars) > 1:
            assert bars[1]["offset_ms"] == bars[0]["duration_ms"]
