"""Sprint 3: Room profiler tests — RT60, noise floor, early-to-late ratio,
room classification.
"""

import numpy as np
import pytest

from acoustic_mirror.analysis.room_profiler import (
    _DEFAULT_RT60,
    RoomProfile,
    RoomProfiler,
    RoomType,
    classify_room,
    estimate_early_to_late_ratio,
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
        decay = _make_decay(0.2, duration=1.0)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert estimate.is_valid
        assert abs(estimate.rt60 - 0.2) < 0.05

    def test_known_rt60_medium(self):
        """RT60 ~ 0.5s medium room."""
        decay = _make_decay(0.5, duration=1.5)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert estimate.is_valid
        assert abs(estimate.rt60 - 0.5) < 0.15

    def test_known_rt60_long(self):
        """RT60 ~ 1.0s reverberant room."""
        decay = _make_decay(1.0, duration=2.5)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert estimate.is_valid
        assert abs(estimate.rt60 - 1.0) < 0.25

    def test_clean_decay_has_high_confidence(self):
        """A clean, noiseless exponential decay should fit the T20 region
        near-perfectly (R^2 close to 1)."""
        decay = _make_decay(0.4, duration=1.0)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert estimate.confidence > 0.9

    def test_truncated_decay_stays_within_tolerance(self):
        """ADR-0003: the Schroeder integral's truncation knee at the tail
        of a short observation window must not bias the estimate, even
        though the knee itself is smooth (high R^2). Truncate a known-RT60
        decay to a short window and check the estimate is still close, not
        silently biased short by the knee.

        Asserts is_valid explicitly (not `if estimate.is_valid: ...`) —
        that conditional form previously let this test pass vacuously
        whenever the estimate was rejected, which is exactly what
        happened with the first (proportional-trim) implementation of
        this fix: it silently accepted a confidently biased-short
        estimate instead of either rejecting it or getting it right.
        """
        full_decay = _make_decay(0.4, duration=1.0)
        truncated = full_decay[: int(0.35 * SAMPLE_RATE)]  # cut well before -60dB
        estimate = estimate_rt60_from_decay(truncated, SAMPLE_RATE)
        assert estimate.is_valid
        assert abs(estimate.rt60 - 0.4) < 0.15

    @pytest.mark.parametrize("dur_ms", [100, 120, 150, 200, 300, 500])
    def test_short_windows_are_accurate_or_self_reject(self, dur_ms):
        """Regression guard for the truncation-knee bias found via advisor
        review: a proportional tail trim let a 100ms window of a true
        0.3s-RT60 decay return rt60=0.2519 at confidence 0.9961 — a
        confidently wrong answer the R^2 gate didn't catch. Every window
        length must now either land close to the true value or reject
        outright; it must never land far off with high confidence.
        """
        true_rt60 = 0.3
        n = int(SAMPLE_RATE * dur_ms / 1000)
        t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
        decay = (0.3 * np.exp(-6.908 * t / true_rt60)).astype(np.float32)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        if estimate.is_valid:
            assert abs(estimate.rt60 - true_rt60) < 0.08

    @pytest.mark.parametrize("true_rt60", [0.15, 0.3, 0.5, 0.8, 1.2, 1.5])
    @pytest.mark.parametrize("dur_ms", [320, 400, 470])
    def test_reachable_across_rt60_range_at_realistic_window_lengths(self, true_rt60, dur_ms):
        """Regression guard for a third advisor-review hypothesis: that
        long RT60s might never validate within the ~320-470ms windows
        _extract_decay_segment can actually produce (a single 500ms
        chunk's remainder — see the reachability sweep in test_main.py),
        making REVERBERANT permanently unreachable the same way the 300ms
        floor made all of RT60 estimation unreachable. Measured: all of
        these combinations are is_valid=True (this test), though long
        RT60s at short windows underestimate — see docs/adr/ADR-0003 for
        the accepted risk that this can misclassify right at the 0.6s
        room-type boundary, which this test does not cover.
        """
        n = int(SAMPLE_RATE * dur_ms / 1000)
        t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
        decay = (0.3 * np.exp(-6.908 * t / true_rt60)).astype(np.float32)
        estimate = estimate_rt60_from_decay(decay, SAMPLE_RATE)
        assert estimate.is_valid

    def test_rt60_clamps_to_valid_range(self):
        """Extreme inputs should produce clamped RT60."""
        # Very fast decay
        fast = _make_decay(0.01, duration=0.3)
        estimate = estimate_rt60_from_decay(fast, SAMPLE_RATE)
        assert estimate.rt60 >= 0.05
        # Very slow decay (nearly constant)
        slow = np.ones(SAMPLE_RATE, dtype=np.float32)
        estimate = estimate_rt60_from_decay(slow, SAMPLE_RATE)
        assert estimate.rt60 <= 3.0

    def test_growing_signal_is_invalid(self):
        """A signal that gets LOUDER over time (Schroeder integral slope
        >= 0, since even backward-integrated energy fails to decrease)
        should be flagged invalid rather than produce a fabricated RT60."""
        n = 8000
        t = np.arange(n, dtype=np.float64) / SAMPLE_RATE
        growing = np.exp(t * 3.0).astype(np.float32)  # amplitude grows over time
        estimate = estimate_rt60_from_decay(growing, SAMPLE_RATE)
        assert estimate.is_valid is False
        assert estimate.rt60 == 3.0

    def test_too_short_signal_is_invalid(self):
        too_short = np.ones(50, dtype=np.float32)
        estimate = estimate_rt60_from_decay(too_short, SAMPLE_RATE)
        assert estimate.is_valid is False


class TestEarlyToLateRatio:
    def test_pure_direct_sound_high_ratio(self):
        """Energy only in first 50ms => high ratio."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.zeros(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        signal[:early] = 1.0
        ratio = estimate_early_to_late_ratio(signal, SAMPLE_RATE, onset=0)
        assert ratio > 10

    def test_pure_reverb_low_ratio(self):
        """Energy only after 50ms => very low ratio."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.zeros(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        signal[early:] = 1.0
        ratio = estimate_early_to_late_ratio(signal, SAMPLE_RATE, onset=0)
        assert ratio < -10

    def test_equal_energy_ratio_is_zero(self):
        """Equal early and late energy => ratio ~ 0dB."""
        n = int(0.2 * SAMPLE_RATE)
        signal = np.ones(n, dtype=np.float32)
        early = int(0.05 * SAMPLE_RATE)
        late = n - early
        # Scale so early_energy == late_energy
        signal[:early] = np.sqrt(late / early)
        signal[early:] = 1.0
        ratio = estimate_early_to_late_ratio(signal, SAMPLE_RATE, onset=0)
        assert abs(ratio) < 1.0


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

    def test_srmr_targets_match_calibrated_values(self):
        """Locks in the specific thresholds calibrated in ADR-0001 against
        this implementation's own output distribution (measured via
        tests/synth.py's synth_speech()/apply_reverb(), 5 seeds per RT60
        condition — see room_profiler.py's _SRMR_TARGETS comment for the
        full table). A future SRMR implementation change that shifts the
        score distribution should also intentionally update these values
        (and re-run the calibration measurement), not silently drift.
        """
        assert RoomType.QUIET_SMALL.srmr_target == pytest.approx(3.3)
        assert RoomType.NOISY_SMALL.srmr_target == pytest.approx(2.3)
        assert RoomType.MEDIUM_ROOM.srmr_target == pytest.approx(2.2)
        assert RoomType.NOISY_MEDIUM.srmr_target == pytest.approx(1.4)
        assert RoomType.REVERBERANT.srmr_target == pytest.approx(1.1)
        assert RoomType.REVERBERANT_NOISY.srmr_target == pytest.approx(0.7)

    def test_srmr_targets_decrease_with_reverberation(self):
        """Independent of the exact calibrated numbers: a quieter/drier
        room type must always have a higher (harder to reach) SRMR target
        than a noisier/more reverberant one — this is the structural
        property the calibration is supposed to preserve.
        """
        assert RoomType.QUIET_SMALL.srmr_target > RoomType.MEDIUM_ROOM.srmr_target > RoomType.REVERBERANT.srmr_target
        assert RoomType.NOISY_SMALL.srmr_target > RoomType.NOISY_MEDIUM.srmr_target > RoomType.REVERBERANT_NOISY.srmr_target
        for quiet, noisy in [
            (RoomType.QUIET_SMALL, RoomType.NOISY_SMALL),
            (RoomType.MEDIUM_ROOM, RoomType.NOISY_MEDIUM),
            (RoomType.REVERBERANT, RoomType.REVERBERANT_NOISY),
        ]:
            assert quiet.srmr_target > noisy.srmr_target


class TestRoomProfiler:
    def test_produces_room_profile(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profile = profiler.current_profile
        assert isinstance(profile, RoomProfile)
        assert hasattr(profile, "rt60")
        assert hasattr(profile, "noise_floor_db")
        assert hasattr(profile, "early_to_late_ratio_db")
        assert hasattr(profile, "room_type")
        assert hasattr(profile, "srmr_target")
        assert hasattr(profile, "rt60_confidence")

    def test_reports_what_the_estimator_sets(self):
        """ADR-0005 moved the pool and the aggregation into
        RollingRT60Estimator; the profiler now only carries the result."""
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.set_rt60(0.3, confidence=0.95)
        assert abs(profiler.current_profile.rt60 - 0.3) < 1e-6
        assert profiler.current_profile.rt60_confidence > 0.9

    def test_an_unmeasured_room_reports_zero_confidence(self):
        """ADR-0005: classify_room still needs a number, so the profile
        carries the default — but confidence 0 marks it as not measured,
        and that is what the dashboard keys off (issue #13)."""
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.set_rt60(0.42, confidence=0.9)

        profiler.set_rt60(None, confidence=0.9)

        assert profiler.current_profile.rt60 == _DEFAULT_RT60
        assert profiler.current_profile.rt60_confidence == 0.0

    def test_update_noise_floor(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.update_noise_floor(-45.0)
        assert profiler.current_profile.noise_floor_db == pytest.approx(-45.0, abs=1)

    def test_update_early_to_late_ratio(self):
        profiler = RoomProfiler(sample_rate=SAMPLE_RATE)
        profiler.update_early_to_late_ratio(8.0)
        assert profiler.current_profile.early_to_late_ratio_db == pytest.approx(8.0, abs=0.1)
