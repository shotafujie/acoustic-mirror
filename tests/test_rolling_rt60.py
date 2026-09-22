"""ADR-0005: streaming RT60 measured on a rolling window.

The path this replaces could only observe a decay when the VAD went from
speech to silence, which a reverberant tail prevents — the more reverberant
the room, the less able it was to measure reverberation (issue #13). These
tests pin the behaviour the new trigger is supposed to have, including the
cases where the old one produced nothing.
"""

from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from acoustic_mirror.analysis import batch_diagnostic, rolling_rt60, room_profiler
from acoustic_mirror.analysis.room_profiler import RoomProfiler
from acoustic_mirror.main import AnalysisPipeline

from acoustic_mirror.analysis.rolling_rt60 import (
    MIN_RT60_EVENTS,
    _POOL_SIZE as POOL_SIZE,
    RollingRT60Estimator,
)
from acoustic_mirror.analysis.speech_detector import SpeechDetector
from tests.synth import apply_reverb, reverberant_utterances, synth_speech

SR = 16000
CHUNK = SR // 2  # the pipeline's 500ms chunk
WINDOW = 3 * SR  # the SRMR ring buffer (ADR-0002), reused by ADR-0005


def _stream(clip, estimator=None, window_samples=WINDOW):
    """Drive a clip through the estimator the way AnalysisPipeline does:
    500ms chunks, each one pushing the latest `window_samples` of history."""
    est = estimator or RollingRT60Estimator(sample_rate=SR)
    for end in range(CHUNK, len(clip) + 1, CHUNK):
        start = max(0, end - window_samples)
        if end - start < window_samples:
            continue  # the ring buffer has not filled yet
        est.push(clip[start:end].astype(np.float32), window_start=start)
    return est


def _vad_transitions(clip):
    """How many speech→silence transitions the old trigger would have seen."""
    det = SpeechDetector(sample_rate=SR)
    prev, count = False, 0
    for i in range(0, len(clip) - CHUNK + 1, CHUNK):
        now = det.process(clip[i : i + CHUNK].astype(np.float32)).is_speech
        if prev and not now:
            count += 1
        prev = now
    return count


class TestAccuracy:
    """V1: every condition of the harness ADR-0003/0004 use for RT60."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    @pytest.mark.parametrize("gap", [0.7, 1.2])
    @pytest.mark.parametrize("true_rt60", [0.3, 0.4, 0.6, 0.8, 1.0])
    def test_reports_within_15_percent(self, true_rt60, gap, seed):
        est = _stream(reverberant_utterances(true_rt60, gap=gap, seed=seed))

        assert est.rt60 is not None, "no estimate at all"
        assert abs(est.rt60 - true_rt60) / true_rt60 <= 0.15


class TestTheCaseTheOldTriggerCouldNotSee:
    """V2: the core of ADR-0005. If this ever passes on the old trigger the
    premise of the ADR is wrong; if it fails, the fix has regressed."""

    @pytest.mark.parametrize("true_rt60", [0.8, 1.0])
    def test_reverberant_room_with_short_pauses_is_measurable(self, true_rt60):
        clip = reverberant_utterances(true_rt60, gap=0.7, seed=1)

        assert _vad_transitions(clip) == 0, (
            "the old speech→silence trigger is supposed to be blind here; "
            "if it now fires, this test no longer pins what it claims to"
        )
        est = _stream(clip)

        assert est.rt60 is not None
        assert abs(est.rt60 - true_rt60) / true_rt60 <= 0.15


class TestRefusalInsteadOfAGuess:
    def test_below_the_event_floor_nothing_is_reported(self):
        """V3: batch refuses under MIN_RT60_EVENTS; streaming now does too,
        instead of publishing a single event as the room (issue #13)."""
        est = RollingRT60Estimator(sample_rate=SR)
        est._accept(0.42)  # one event, whatever it says

        assert est.event_count == 1
        assert est.rt60 is None
        assert est.confidence == 0.0

    def test_confidence_stays_zero_until_the_floor_is_reached(self):
        est = RollingRT60Estimator(sample_rate=SR)
        for _ in range(MIN_RT60_EVENTS - 1):
            est._accept(0.42, r_squared=0.99)
            assert est.confidence == 0.0
        est._accept(0.42, r_squared=0.99)

        assert est.rt60 is not None
        assert est.confidence > 0.0

    def test_continuous_speech_produces_no_room_estimate(self):
        """V6: with no pauses there is no free decay to observe. Reporting
        anything here would be reporting the voice, not the room."""
        est = _stream(apply_reverb(synth_speech(dur=7.0, seed=42), 0.6))

        assert est.rt60 is None


class TestEachDecayCountsOnce:
    def test_an_event_seen_in_six_windows_is_adopted_once(self):
        """V4: the window advances 500ms at a time, so one decay appears in
        up to six consecutive windows.

        The count is asserted exactly, not against a re-run of the same
        clip: with deduplication broken the pool saturates at its maximum
        and any before/after comparison holds anyway (found by the
        independent verification of ADR-0005).
        """
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)

        est = _stream(clip)

        # Five decays are present in this clip; without deduplication the
        # same ones are re-fitted in every window that contains them and
        # the pool fills to _POOL_SIZE.
        assert est.event_count == 5
        assert est.event_count < POOL_SIZE

    def test_an_origin_that_moves_by_one_frame_is_still_one_event(self):
        """The decay origin is found against percentiles recomputed for each
        window, so the same decay can be located a frame earlier or later as
        the window slides. Events are at least 100ms long, so two keys 10ms
        apart are the same decay, not two."""
        est = RollingRT60Estimator(sample_rate=SR)
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        window = clip[: 3 * SR].astype(np.float32)

        est.push(window, window_start=0)
        before = est.event_count
        est.push(window, window_start=int(0.01 * SR))  # everything shifted 10ms

        assert est.event_count == before

    def test_the_dedupe_keys_do_not_grow_with_session_length(self):
        """The monitor runs for as long as a call does. Keys for decays that
        ended before the current window can never match again."""
        est = RollingRT60Estimator(sample_rate=SR)
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        period = len(clip) - 3 * SR

        for lap in range(20):  # ~2.5 minutes of audio
            for offset in range(0, period, CHUNK):
                est.push(
                    clip[offset : offset + 3 * SR].astype(np.float32),
                    window_start=lap * period + offset,
                )

        assert len(est._seen) <= 3 * SR // est._key_size

    def test_repushing_the_same_window_adds_nothing(self):
        """The same window can be offered twice — the loop pushes whatever
        the ring buffer holds, whether or not it advanced."""
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        window = clip[: 3 * SR].astype(np.float32)
        est = RollingRT60Estimator(sample_rate=SR)

        est.push(window, window_start=0)
        before = est.event_count
        est.push(window, window_start=0)

        assert before > 0, "nothing was adopted; the test is vacuous"
        assert est.event_count == before
    def test_an_event_still_running_at_the_window_edge_waits(self):
        """V5: a decay cut off by the edge would be fitted over a fraction of
        its length and read short."""
        decay = np.concatenate(
            [
                np.zeros(SR, dtype=np.float32),
                (0.5 * np.exp(-6.908 * np.arange(SR) / SR / 0.8)).astype(np.float32),
            ]
        )
        noise = 1e-3 * np.random.default_rng(0).standard_normal(len(decay)).astype(np.float32)
        clip = decay + noise

        cut = RollingRT60Estimator(sample_rate=SR)
        cut.push(clip[: int(1.2 * SR)], window_start=0)  # decay still falling at the edge

        assert cut.event_count == 0




class TestTheConfidenceGateSurvivedTheMove:
    """ADR-0003 put an R^2 gate in RoomProfiler.update_rt60 so a noisy fit
    could not move rt60. ADR-0005 moved the pool into the estimator; the
    gate had to come with it.

    A decay whose T20 fit is genuinely poor is hard to synthesize — the
    Schroeder integral is monotonic by construction, so R^2 comes out high
    on almost anything the event detector will hand over (ADR-0004 recorded
    the same thing: 0 rejections in 22 of 24 conditions). So rather than
    fake a signal, these pin the two things that can actually break: that
    the gate is consulted at all, and that it is set to the value ADR-0003
    chose.
    """

    def test_the_gate_is_consulted_when_events_are_adopted(self):
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        assert _stream(clip).event_count > 0, "nothing to gate; test is vacuous"

        with mock.patch.object(rolling_rt60, "_RT60_CONFIDENCE_MIN", 1.01):
            strict = _stream(clip)

        assert strict.event_count == 0, "events were adopted past an impossible gate"
        assert strict.rejected_count > 0, "they were not even counted as rejected"
        assert strict.rt60 is None

    def test_the_gate_is_the_one_adr_0003_set(self):
        """Pins the value too: a test that only patches the constant would
        still pass if the default were lowered to accept everything."""
        assert rolling_rt60._RT60_CONFIDENCE_MIN == room_profiler._RT60_CONFIDENCE_MIN
        assert rolling_rt60._RT60_CONFIDENCE_MIN == 0.5


class TestAggregation:
    """ADR-0005 論点3 measured pool=10 / p70 against pool=5 and p50. Nothing
    was pinning either number: the independent verification swapped them for
    the rejected combination and all 312 tests still passed."""

    def test_the_pool_holds_ten(self):
        est = RollingRT60Estimator(sample_rate=SR)
        for i in range(12):
            est._accept(0.1 * (i + 1))

        assert est.event_count == POOL_SIZE == 10

    def test_aggregation_is_the_70th_percentile(self):
        values = [0.30, 0.32, 0.35, 0.40, 0.50]
        est = RollingRT60Estimator(sample_rate=SR)
        for v in values:
            est._accept(v)

        assert est.rt60 == pytest.approx(float(np.percentile(values, 70)))
        # The median — what the streaming path used before ADR-0005 — is a
        # different number on this pool, so the assertion above is not
        # satisfied by both.
        assert est.rt60 != pytest.approx(float(np.median(values)))

    def test_confidence_is_the_pools_median_r_squared(self):
        est = RollingRT60Estimator(sample_rate=SR)
        for r2 in (0.6, 0.7, 0.95, 0.99):
            est._accept(0.4, r_squared=r2)

        assert est.confidence == pytest.approx(0.825)  # median of the four


class TestTheEventDetectorIsSharedNotCopied:
    """ADR-0005 設計1: import find_decay_events rather than reimplement it,
    so the two paths cannot drift apart."""

    def test_it_is_the_same_function_object_the_batch_path_uses(self):
        assert rolling_rt60.find_decay_events is batch_diagnostic.find_decay_events

    def test_the_module_does_not_define_its_own(self):
        source = Path(rolling_rt60.__file__).read_text(encoding="utf-8")
        assert "def find_decay_events" not in source


class TestTheOldTriggerIsGone:
    """ADR-0005 設計2: the VAD-transition path is removed, not left running
    beside the new one — both would adopt the same decay twice."""

    @pytest.mark.parametrize(
        "attribute", ["_extract_decay_segment", "_find_speech_offset", "_prev_chunk"]
    )
    def test_the_pipeline_no_longer_has_it(self, attribute):
        assert not hasattr(AnalysisPipeline(sample_rate=SR), attribute)

    def test_the_profiler_no_longer_accumulates_estimates(self):
        profiler = RoomProfiler(sample_rate=SR)

        assert not hasattr(profiler, "update_rt60")
        assert not hasattr(profiler, "_rt60_estimates")
