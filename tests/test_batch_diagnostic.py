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
from acoustic_mirror.analysis.room_profiler import (
    _RT60_CONFIDENCE_MIN,
    estimate_early_to_late_ratio,
    estimate_rt60_from_decay,
)
from acoustic_mirror.analysis.speech_detector import frame_energy_db
from acoustic_mirror.analysis.srmr import SRMRProcessor
from tests.synth import (
    SAMPLE_RATE,
    apply_reverb,
    reverberant_speech,
    reverberant_utterances,
    speech_utterances,
    synth_speech,
    synth_utterances,
)


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

    def test_srmr_computed_when_pauses_lower_the_ratio(self):
        """The pauses RT60 needs must not cost us SRMR (ADR-0004 revision).

        gap=0.7 is the recording protocol the diagnose page asks for. It puts
        the speech ratio well under the streaming path's 0.7 gate while still
        holding more than SRMR's 3s window worth of speech.
        """
        y = reverberant_utterances(0.3, gap=0.7, seed=1)
        result = diagnose(y, SAMPLE_RATE)
        assert result.speech_ratio < 0.7
        assert result.speech_seconds >= MIN_DURATION_SECONDS
        assert result.srmr_score is not None

    def test_srmr_skipped_when_speech_shorter_than_srmr_window(self):
        """Gate on seconds of speech, not on the ratio: pauses long enough to
        leave under 3s of speech still fail SRMR's premise (ADR-0002)."""
        y = reverberant_utterances(0.3, gap=1.2, seed=1)
        result = diagnose(y, SAMPLE_RATE)
        assert result.speech_seconds < MIN_DURATION_SECONDS
        assert result.srmr_score is None

    def test_srmr_skipped_when_clip_is_short_despite_high_ratio(self):
        """A high ratio over a short clip is not enough speech for SRMR."""
        y = reverberant_utterances(0.3, gap=0.2, seed=1)[: int(3.5 * SAMPLE_RATE)]
        result = diagnose(y, SAMPLE_RATE)
        assert result.speech_ratio >= 0.7
        assert result.speech_seconds < MIN_DURATION_SECONDS
        assert result.srmr_score is None

    def test_srmr_skipped_when_mostly_silent(self):
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(5 * SAMPLE_RATE)).astype(np.float32)
        result = diagnose(y, SAMPLE_RATE)
        assert result.speech_seconds < MIN_DURATION_SECONDS
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


class TestDecayEventGating:
    """Promises D3b / D6: which decay events reach the aggregate."""

    def test_only_gate_passing_events_are_aggregated(self):
        """The accepted set is exactly the events whose fit clears the
        streaming path's gate, and the rest are counted as rejected."""
        # The flat-burst harness never trips the gate (every event fits
        # cleanly), so it cannot verify that rejection happens at all. The
        # speech-content harness produces both outcomes.
        y = reverberant_speech(0.5, dur=7.0, burst=1.5, gap=1.0, seed=1)
        accepted, rejected = [], 0
        for start, end in find_decay_events(y, SAMPLE_RATE):
            est = estimate_rt60_from_decay(y[start:end], SAMPLE_RATE)
            if est.is_valid and est.confidence >= _RT60_CONFIDENCE_MIN:
                accepted.append(est.rt60)
            else:
                rejected += 1
        result = diagnose(y, SAMPLE_RATE)
        assert rejected > 0, "clip must actually exercise the gate"
        assert result.rt60_events == pytest.approx(accepted)
        assert result.rt60_rejected_count == rejected

    def test_events_are_never_shorter_than_100ms(self):
        for rt60, gap in ((0.3, 0.7), (0.6, 0.7), (1.5, 1.2)):
            y = reverberant_utterances(rt60, gap=gap, seed=1)
            for start, end in find_decay_events(y, SAMPLE_RATE):
                assert (end - start) / SAMPLE_RATE >= 0.1

    def test_sub_100ms_decay_is_not_an_event(self):
        """A burst whose decay reaches the floor in ~60ms yields no event."""
        rng = np.random.default_rng(0)
        y = (1e-3 * rng.standard_normal(5 * SAMPLE_RATE)).astype(np.float32)
        for t in (0.5, 1.5, 2.5, 3.5):
            a = int(t * SAMPLE_RATE)
            n = int(0.06 * SAMPLE_RATE)
            y[a : a + n] += (0.3 * rng.standard_normal(n) * np.linspace(1, 0, n)).astype(np.float32)
        for start, end in find_decay_events(y, SAMPLE_RATE):
            assert (end - start) / SAMPLE_RATE >= 0.1


class TestNoiseFloorAndSpeech:
    """Promise D2: energies and floor come from the whole clip at once."""

    def _expected_floor(self, y):
        frame = int(SAMPLE_RATE * 0.03)  # 30ms
        n = len(y) // frame
        e = [frame_energy_db(y[i * frame : (i + 1) * frame]) for i in range(n)]
        return float(np.percentile(e, 10))

    def test_floor_is_the_tenth_percentile_of_30ms_frames(self):
        y = reverberant_utterances(0.6, gap=0.7, seed=1)
        result = diagnose(y, SAMPLE_RATE)
        assert result.noise_floor_db == pytest.approx(self._expected_floor(y))

    def test_floor_does_not_depend_on_an_adaptive_estimate_converging(self):
        """SpeechDetector's floor adapts over time and has not converged at
        the start of a clip (ADR-0004). A clip that opens at full level must
        still report the whole-clip floor."""
        y = reverberant_utterances(0.6, gap=0.7, seed=1)
        loud_first = np.concatenate([y[: 2 * SAMPLE_RATE], y]).astype(np.float32)
        result = diagnose(loud_first, SAMPLE_RATE)
        assert result.noise_floor_db == pytest.approx(self._expected_floor(loud_first))

    def test_speech_seconds_is_the_speech_frames_duration(self):
        y = reverberant_utterances(0.3, gap=0.7, seed=1)
        result = diagnose(y, SAMPLE_RATE)
        assert result.speech_seconds == pytest.approx(
            result.speech_ratio * (len(y) // int(SAMPLE_RATE * 0.03)) * 0.03, rel=1e-6
        )


class TestAggregationChoices:
    """Promises D8 / V4: how the per-event values are combined."""

    def test_early_to_late_is_the_median_not_the_mean(self):
        y = reverberant_utterances(0.3, gap=0.7, seed=1)  # 6 isolated onsets
        result = diagnose(y, SAMPLE_RATE)
        frame = int(SAMPLE_RATE * 0.03)
        e = np.array(
            [frame_energy_db(y[i * frame : (i + 1) * frame]) for i in range(len(y) // frame)]
        )
        is_speech = e > float(np.percentile(e, 10)) + 6.0
        n_iso = max(1, round(200.0 / 30))
        onsets = [
            i for i in range(n_iso, len(is_speech)) if is_speech[i] and not is_speech[i - n_iso : i].any()
        ]
        ratios = [estimate_early_to_late_ratio(y, SAMPLE_RATE, onset=i * frame) for i in onsets]
        assert len(ratios) >= 3
        assert np.median(ratios) != pytest.approx(np.mean(ratios)), "clip must tell them apart"
        assert result.early_to_late_ratio_db == pytest.approx(float(np.median(ratios)))

    @pytest.mark.parametrize("rt60", [1.0, 1.5])
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_70th_percentile_beats_the_median_on_truncated_tails(self, rt60, seed):
        """Why 70 and not 50 (ADR-0004).

        The failure mode the percentile has to survive is a tail cut short
        by the next utterance, which drags individual fits downward. With
        0.7s pauses — the protocol the diagnose page asks for — 70 is
        closer to the true value than the median for every long RT60 and
        seed measured.
        """
        result = diagnose(reverberant_utterances(rt60, gap=0.7, seed=seed), SAMPLE_RATE)
        assert len(result.rt60_events) >= 3
        p50 = float(np.percentile(result.rt60_events, 50))
        p70 = float(np.percentile(result.rt60_events, 70))
        assert abs(p70 - rt60) < abs(p50 - rt60)

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_70th_percentile_overshoots_when_tails_are_not_truncated(self, seed):
        """The other side of that choice, pinned so it is not forgotten.

        Given pauses long enough to observe the whole tail (1.2s) at
        RT60=1.0, the median is the closer of the two and 70 reads high.
        ADR-0004 keeps 70 because truncated tails are the realistic case,
        not because 70 is closer everywhere.
        """
        result = diagnose(reverberant_utterances(1.0, gap=1.2, seed=seed), SAMPLE_RATE)
        assert len(result.rt60_events) >= 3
        p50 = float(np.percentile(result.rt60_events, 50))
        p70 = float(np.percentile(result.rt60_events, 70))
        assert p70 > 1.0
        assert abs(p50 - 1.0) < abs(p70 - 1.0)


class TestFalsifiabilityConditions:
    """Promise V3: the condition ADR-0004 said would falsify it."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_rt60_1s_with_long_pauses_within_15_percent(self, seed):
        result = diagnose(reverberant_utterances(1.0, gap=1.2, seed=seed), SAMPLE_RATE)
        assert result.rt60 is not None
        assert abs(result.rt60 - 1.0) / 1.0 <= 0.15


class TestCauseDiagnosis:
    """Promise D12: the batch path runs the existing cause separator."""

    def test_cause_reported_when_srmr_is_below_target(self):
        result = diagnose(reverberant_speech(1.5, dur=10.0, burst=2.0, gap=1.2, seed=1), SAMPLE_RATE)
        assert result.srmr_score is not None
        assert result.srmr_score < result.room_profile.srmr_target
        assert result.cause is not None
        assert result.cause.primary_cause is not None
        assert "primary_cause" in result.to_dict()


class TestNoOverallScore:
    """Promise I4: no MOS-style overall score, now or later."""

    def test_no_mos_conversion_in_the_source(self):
        import pathlib
        import re

        src = pathlib.Path(__file__).resolve().parents[1] / "src"
        hits = [
            f"{path.relative_to(src)}:{i}"
            for path in src.rglob("*.py")
            for i, line in enumerate(path.read_text().splitlines(), 1)
            if re.search(r"\brtomos\b|\bmos_score\b|\bto_mos\b", line, re.IGNORECASE)
        ]
        assert hits == [], f"MOS conversion reintroduced (ADR-0004 rejects it): {hits}"


class TestSRMRGateJustification:
    """Promise V5: the evidence ADR-0004's gate revision was decided on.

    `TestSRMRAndRoom` pins what the gate *does*. This pins *why* it was
    changed, so the reasoning can be falsified rather than only recited.
    """

    # The recording protocols measured in ADR-0004: (burst, gap, duration).
    PROTOCOLS = [(1.5, 1.0, 7.0), (2.0, 0.7, 7.0), (2.0, 0.7, 10.0), (3.0, 1.0, 10.0), (2.5, 0.5, 7.0)]
    TRUE_RT60 = 0.5

    def _clip(self, burst, gap, dur, seed=1):
        return reverberant_speech(self.TRUE_RT60, dur=dur, burst=burst, gap=gap, seed=seed)

    def _srmr(self, y):
        r = SRMRProcessor(sample_rate=SAMPLE_RATE).process(y, is_speech=True)
        return r.srmr_score if r.is_valid else None

    @pytest.mark.parametrize("burst,gap,dur", PROTOCOLS)
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_srmr_survives_every_realistic_protocol(self, burst, gap, dur, seed):
        """Whatever way the user obeys "leave a pause between sentences",
        the clip still holds enough speech for SRMR."""
        result = diagnose(self._clip(burst, gap, dur, seed), SAMPLE_RATE)
        assert result.speech_seconds >= MIN_DURATION_SECONDS
        assert result.srmr_score is not None

    def test_the_old_ratio_gate_would_have_rejected_some_of_them(self):
        """The reason the ratio gate had to go: it is a coin flip across
        protocols a user cannot tell apart."""
        ratios = [diagnose(self._clip(*p), SAMPLE_RATE).speech_ratio for p in self.PROTOCOLS]
        assert min(ratios) < 0.7, f"no protocol falls below the old gate: {ratios}"
        assert max(ratios) >= 0.7, f"no protocol clears the old gate: {ratios}"

    @pytest.mark.parametrize("burst,gap,dur", PROTOCOLS)
    def test_pauses_barely_move_srmr(self, burst, gap, dur):
        """The core claim behind the revision: the silence the ratio gate
        was protecting against is not actually corrupting the score.

        Reference is the same room heard without pauses. Measured deviation
        across protocols and seeds was at most 5.5%.
        """
        reference = self._srmr(apply_reverb(synth_speech(dur=7.0), self.TRUE_RT60))
        score = diagnose(self._clip(burst, gap, dur), SAMPLE_RATE).srmr_score
        assert abs(score - reference) / reference <= 0.10

    def test_densest_3s_window_is_the_noisier_alternative(self):
        """Why the rejected option was rejected: a 3s window swings more
        than the whole clip it would replace."""
        whole, windowed = [], []
        for burst, gap, dur in self.PROTOCOLS:
            for seed in (1, 2, 3):
                y = self._clip(burst, gap, dur, seed)
                whole.append(diagnose(y, SAMPLE_RATE).srmr_score)
                e = np.array([
                    frame_energy_db(y[i * 480 : (i + 1) * 480]) for i in range(len(y) // 480)
                ])
                is_speech = e > float(np.percentile(e, 10)) + 6.0
                n = 3 * SAMPLE_RATE
                best = max(
                    range(0, max(1, len(y) - n + 1), SAMPLE_RATE // 4),
                    key=lambda st: is_speech[st // 480 : (st + n) // 480].mean(),
                )
                windowed.append(self._srmr(y[best : best + n]))
        assert max(whole) - min(whole) < max(windowed) - min(windowed)

    def test_srmr_is_computed_on_the_whole_clip(self):
        """Promise D10: the whole recording, one pass — not a sub-window.

        Distinguishes the two candidates by value, which `is not None`
        cannot do.
        """
        y = self._clip(1.5, 1.0, 7.0)
        assert diagnose(y, SAMPLE_RATE).srmr_score == pytest.approx(self._srmr(y))

    def test_this_harness_cannot_measure_rt60(self):
        """A boundary, pinned so nobody adds an RT60 assertion here.

        `speech_utterances` carries synth_speech's 4Hz envelope, whose
        nulls read as decays: the dry signal alone yields accepted RT60
        events with no room at all. RT60 accuracy belongs to the flat-burst
        harness (`reverberant_utterances`), which yields none when dry.
        """
        dry = speech_utterances(dur=7.0, burst=1.5, gap=1.0, seed=1)
        noise = 1e-3 * np.random.default_rng(99).standard_normal(len(dry))
        y = (dry + noise).astype(np.float32)
        accepted = [
            est.rt60
            for start, end in find_decay_events(y, SAMPLE_RATE)
            for est in [estimate_rt60_from_decay(y[start:end], SAMPLE_RATE)]
            if est.is_valid and est.confidence >= _RT60_CONFIDENCE_MIN
        ]
        assert accepted, "harness no longer self-decays; revisit this boundary"

        flat = synth_utterances(dur=7.0, burst=0.3, gap=0.7, seed=1)
        flat = (flat + noise[: len(flat)]).astype(np.float32)
        assert find_decay_events(flat, SAMPLE_RATE) == []
