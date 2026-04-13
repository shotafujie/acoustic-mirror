"""Sprint 3: Room profiler tests — RT60, noise floor, DRR, room classification."""

import numpy as np
import pytest

from acoustic_mirror.analysis.room_profiler import (
    RoomProfile,
    RoomProfiler,
    RoomType,
    classify_room,
    estimate_drr,
    estimate_rt60_from_decay,
)

SAMPLE_RATE = 16000


def _make_decay(rt60: float, duration: float = 0.5) -> np.ndarray:
    """Synthetic exponential energy decay with known RT60."""
    n = int(duration * SAMPLE_RATE)
    t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
    # RT60: time for energy to drop 60dB => amplitude drops by 10^(-3)
    # amplitude = exp(-t * ln(1000) / rt60)
    decay = np.exp(-t * np.log(1000) / rt60)
    return decay.astype(np.float32)


class TestRT60Estimation:
    def test_known_rt60_short(self):
        """RT60 ~ 0.2s dry room."""
        decay = _make_decay(0.2)
        rt60 = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert abs(rt60 - 0.2) < 0.05

    def test_known_rt60_medium(self):
        """RT60 ~ 0.5s medium room."""
        decay = _make_decay(0.5, duration=1.0)
        rt60 = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert abs(rt60 - 0.5) < 0.1

    def test_known_rt60_long(self):
        """RT60 ~ 1.0s reverberant room."""
        decay = _make_decay(1.0, duration=2.0)
        rt60 = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert abs(rt60 - 1.0) < 0.2

    def test_rt60_clamps_to_valid_range(self):
        """Extreme inputs should produce clamped RT60."""
        # Very fast decay
        fast = _make_decay(0.01)
        rt60 = estimate_rt60_from_decay(fast, SAMPLE_RATE)
        assert rt60 >= 0.05
        # Very slow decay (nearly constant)
        slow = np.ones(SAMPLE_RATE, dtype=np.float32)
        rt60 = estimate_rt60_from_decay(slow, SAMPLE_RATE)
        assert rt60 <= 3.0

    def test_constant_signal_returns_max_rt60(self):
        """A constant signal has no decay — should return max clamp."""
        const = np.ones(8000, dtype=np.float32)
        rt60 = estimate_rt60_from_decay(const, SAMPLE_RATE)
        assert rt60 == 3.0


class TestDRR:
    def test_pure_direct_sound_high_drr(self):
        """Energy only in first 50ms => high DRR."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.zeros(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        signal[:early] = 1.0
        drr = estimate_drr(signal, SAMPLE_RATE, onset=0)
        assert drr > 10

    def test_pure_reverb_low_drr(self):
        """Energy only after 50ms => very low DRR."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.zeros(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        signal[early:] = 1.0
        drr = estimate_drr(signal, SAMPLE_RATE, onset=0)
        assert drr < -10

    def test_equal_energy_drr_is_zero(self):
        """Equal early and late energy => DRR ~ 0dB."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.ones(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        late = n - early
        # Scale so early_energy == late_energy
        signal[:early] = np.sqrt(late / early)
        signal[early:] = 1.0
        drr = estimate_drr(signal, SAMPLE_RATE, onset=0)
        assert abs(drr) < 1.0


class TestRoomClassification:
    @pytest.mark.parametrize(
        "rt60, noise_db, expected",
        [
            (0.15, -50, RoomType.QUIET_SMALL),
            (0.15, -30, RoomType.NOISY_SMALL),
            (0.4, -40, RoomType.MEDIUM_ROOM),
            (0.4, -20, RoomType.NOISY_MEDIUM),
            (0.8, -40, RoomType.REVERBERANT),
            (0.8, -20, RoomType.REVERBERANT_NOISY),
        ],
    )
    def test_room_classification(self, rt60, noise_db, expected):
        assert classify_room(rt60, noise_db) == expected

    def test_all_room_types_have_srmr_target(self):
        for rt in RoomType:
            assert rt.srmr_target > 0


class TestRoomProfiler:
    def test_produces_room_profile(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profile = profiler.current_profile
        assert isinstance(profile, RoomProfile)
        assert hasattr(profile, "rt60")
        assert hasattr(profile, "noise_floor_db")
        assert hasattr(profile, "drr_db")
        assert hasattr(profile, "room_type")
        assert hasattr(profile, "srmr_target")

    def test_update_with_decay_segment(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        decay = _make_decay(0.3)
        profiler.update_rt60(decay)
        assert abs(profiler.current_profile.rt60 - 0.3) < 0.1

    def test_update_noise_floor(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.update_noise_floor(-45.0)
        assert profiler.current_profile.noise_floor_db == pytest.approx(-45.0, abs=1)

    def test_update_drr(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.update_drr(8.0)
        assert profiler.current_profile.drr_db == pytest.approx(8.0, abs=0.1)
