"""Thread-safe ring buffer for accumulating audio chunks."""

import threading

import numpy as np


class RingBuffer:
    """Fixed-size circular buffer for streaming audio data.

    Audio callback writes chunks from a separate thread; the main analysis
    thread reads the latest window_size samples via get_window().
    """

    def __init__(self, window_size: int = 8000) -> None:
        self._window_size = window_size
        self._buf = np.zeros(window_size, dtype=np.float32)
        self._write_pos = 0
        self._total_written = 0
        self._lock = threading.Lock()

    @property
    def has_enough_data(self) -> bool:
        return self._total_written >= self._window_size

    def write(self, data: np.ndarray) -> None:
        """Append samples to the ring buffer (thread-safe)."""
        n = len(data)
        with self._lock:
            if n >= self._window_size:
                # Only keep the last window_size samples
                self._buf[:] = data[-self._window_size :]
                self._write_pos = 0
                self._total_written += n
                return

            end = self._write_pos + n
            if end <= self._window_size:
                self._buf[self._write_pos : end] = data
            else:
                first = self._window_size - self._write_pos
                self._buf[self._write_pos :] = data[:first]
                self._buf[: n - first] = data[first:]
            self._write_pos = end % self._window_size
            self._total_written += n

    def get_window(self) -> np.ndarray:
        """Return the latest window_size samples as a contiguous copy."""
        with self._lock:
            if self._total_written == 0:
                return np.zeros(self._window_size, dtype=np.float32)
            # Reorder so that oldest sample is at index 0
            out = np.empty(self._window_size, dtype=np.float32)
            out[: self._window_size - self._write_pos] = self._buf[self._write_pos :]
            out[self._window_size - self._write_pos :] = self._buf[: self._write_pos]
            return out
