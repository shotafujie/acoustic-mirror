"""ADR-0005: streaming RT60 measured on a rolling window.

The path this replaces could only observe a decay when the VAD went from
speech to silence, which a reverberant tail prevents — the more reverberant
the room, the less able it was to measure reverberation (issue #13). These
tests pin the behaviour the new trigger is supposed to have, including the
cases where the old one produced nothing.
"""

import numpy as np
import pytest

from acoustic_mirror.analysis.rolling_rt60 import MIN_RT60_EVENTS, RollingRT60Estimator
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
        up to six consecutive windows."""
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        est = _stream(clip)

        # Re-pushing the very same windows must not add anything.
        before = est.event_count
        _stream(clip, estimator=est)

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
    could not move rt60. ADR-0005 moved the pool here; the gate has to come
    with it, or the move quietly dropped a promise."""

    def test_noise_does_not_enter_the_pool(self):
        rng = np.random.default_rng(7)
        noise = rng.standard_normal(3 * SR).astype(np.float32) * 0.1

        est = RollingRT60Estimator(sample_rate=SR)
        est.push(noise, window_start=0)

        assert est.event_count == 0
        assert est.rt60 is None

    def test_a_rejected_event_is_counted_not_silently_dropped(self):
        """Rejections are the evidence the gate is doing anything; the batch
        diagnostic reports them for the same reason (ADR-0004)."""
        clip = reverberant_utterances(0.6, gap=1.2, seed=1)
        noisy = clip + 0.05 * np.random.default_rng(3).standard_normal(len(clip)).astype(np.float32)

        est = _stream(noisy)

        assert est.rejected_count > 0
