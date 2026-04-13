"""Sprint 1: Ring buffer tests."""

import threading

import numpy as np
import pytest

from acoustic_mirror.audio.buffer import RingBuffer


class TestRingBuffer:
    def test_empty_buffer_returns_zeros(self):
        buf = RingBuffer(window_size=8000)
        window = buf.get_window()
        assert window.shape == (8000,)
        np.testing.assert_array_equal(window, np.zeros(8000))

    def test_has_enough_data_initially_false(self):
        buf = RingBuffer(window_size=8000)
        assert buf.has_enough_data is False

    def test_write_exact_window(self):
        buf = RingBuffer(window_size=100)
        data = np.arange(100, dtype=np.float32)
        buf.write(data)
        np.testing.assert_array_equal(buf.get_window(), data)

    def test_has_enough_data_after_fill(self):
        buf = RingBuffer(window_size=100)
        buf.write(np.ones(100, dtype=np.float32))
        assert buf.has_enough_data is True

    def test_write_less_than_window_pads_with_zeros(self):
        buf = RingBuffer(window_size=100)
        data = np.ones(30, dtype=np.float32)
        buf.write(data)
        window = buf.get_window()
        # First 70 should be zeros, last 30 should be ones
        np.testing.assert_array_equal(window[:70], np.zeros(70))
        np.testing.assert_array_equal(window[70:], np.ones(30))

    def test_write_more_than_window_keeps_latest(self):
        buf = RingBuffer(window_size=100)
        data = np.arange(200, dtype=np.float32)
        buf.write(data)
        np.testing.assert_array_equal(buf.get_window(), data[100:])

    def test_multiple_small_writes_accumulate(self):
        buf = RingBuffer(window_size=100)
        for i in range(10):
            buf.write(np.full(10, i, dtype=np.float32))
        expected = np.concatenate([np.full(10, i, dtype=np.float32) for i in range(10)])
        np.testing.assert_array_equal(buf.get_window(), expected)

    def test_wraparound_preserves_latest_data(self):
        buf = RingBuffer(window_size=100)
        # Fill buffer completely
        buf.write(np.zeros(100, dtype=np.float32))
        # Write more to force wrap
        new_data = np.arange(60, dtype=np.float32)
        buf.write(new_data)
        window = buf.get_window()
        # Last 60 samples should be new_data
        np.testing.assert_array_equal(window[40:], new_data)
        # First 40 should be zeros (from original fill)
        np.testing.assert_array_equal(window[:40], np.zeros(40))

    def test_get_window_returns_copy(self):
        buf = RingBuffer(window_size=100)
        buf.write(np.ones(100, dtype=np.float32))
        w1 = buf.get_window()
        w1[:] = 0  # mutate the copy
        w2 = buf.get_window()
        np.testing.assert_array_equal(w2, np.ones(100))

    def test_thread_safety_concurrent_writes(self):
        buf = RingBuffer(window_size=1000)
        errors = []

        def writer(value, count):
            try:
                for _ in range(count):
                    buf.write(np.full(10, value, dtype=np.float32))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(1.0, 100)),
            threading.Thread(target=writer, args=(2.0, 100)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        window = buf.get_window()
        assert window.shape == (1000,)
        # All values should be either 1.0 or 2.0 (no corruption)
        assert np.all((window == 1.0) | (window == 2.0) | (window == 0.0))
