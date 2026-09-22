"""Streaming RT60 measured on a rolling window (ADR-0005).

The streaming path used to estimate RT60 only when the VAD went from speech
to silence, reading the decay from the tail of one 500ms chunk. A reverberant
tail keeps `is_speech` from going False, so the more reverberant the room,
the fewer estimates it produced — none at all past RT60 0.8s with short
pauses (issue #13).

Here the trigger is the decay itself: the same event detector the batch
diagnostic uses (ADR-0004) runs over the 3s window that already exists for
SRMR (ADR-0002), and every event it finds is gated exactly as the streaming
path gated its single event.
"""

from collections import deque

import numpy as np

from acoustic_mirror.analysis.batch_diagnostic import find_decay_events
from acoustic_mirror.analysis.room_profiler import (
    _RT60_CONFIDENCE_MIN,
    estimate_rt60_from_decay,
)

MIN_RT60_EVENTS = 3  # same floor as the batch diagnostic (ADR-0004)
_POOL_SIZE = 10  # ~10s of events; measured against 5 and unbounded (ADR-0005)
_PERCENTILE = 70  # measured against 50 (ADR-0005, and ADR-0004 before it)
_DEDUPE_RESOLUTION_MS = 10  # one decay is seen by up to six overlapping windows


class RollingRT60Estimator:
    """Collects gated RT60 estimates from decay events in a rolling window."""

    def __init__(self, sample_rate: int = 16000) -> None:
        self._sample_rate = sample_rate
        self._estimates: deque[float] = deque(maxlen=_POOL_SIZE)
        self._r_squared: deque[float] = deque(maxlen=_POOL_SIZE)
        self._seen: set[int] = set()
        self._rejected = 0

    def push(self, window: np.ndarray, window_start: int) -> None:
        """Offer the latest window. `window_start` is its first sample's
        position in the stream, which is what keeps one decay from being
        counted once per window it appears in."""
        for start, end in find_decay_events(window, self._sample_rate):
            if end >= len(window):
                # Still falling at the edge: fitting it now would measure a
                # fraction of the decay and read short. It will be complete
                # in a later window.
                continue
            key = (window_start + start) // (self._sample_rate * _DEDUPE_RESOLUTION_MS // 1000)
            if key in self._seen:
                continue
            self._seen.add(key)
            estimate = estimate_rt60_from_decay(window[start:end], self._sample_rate)
            if estimate.is_valid and estimate.confidence >= _RT60_CONFIDENCE_MIN:
                self._accept(estimate.rt60, estimate.confidence)
            else:
                self._rejected += 1

    def _accept(self, rt60: float, r_squared: float = 1.0) -> None:
        self._estimates.append(rt60)
        self._r_squared.append(r_squared)

    @property
    def event_count(self) -> int:
        return len(self._estimates)

    @property
    def rejected_count(self) -> int:
        return self._rejected

    @property
    def rt60(self) -> float | None:
        """None until enough events agree — one event is not a room."""
        if len(self._estimates) < MIN_RT60_EVENTS:
            return None
        return float(np.percentile(list(self._estimates), _PERCENTILE))

    @property
    def confidence(self) -> float:
        """Zero while the pool is too small, so "not measured" is visible
        downstream without RoomProfile.rt60 having to become optional."""
        if len(self._estimates) < MIN_RT60_EVENTS:
            return 0.0
        return float(np.median(list(self._r_squared)))
