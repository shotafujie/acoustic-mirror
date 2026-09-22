"""Sprint 7: Audio capture tests (sounddevice mocked)."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from acoustic_mirror.audio.buffer import RingBuffer
from acoustic_mirror.audio.capture import list_devices, open_stream


class TestAudioCapture:
    @patch("acoustic_mirror.audio.capture.sd")
    def test_open_stream_returns_input_stream(self, mock_sd):
        mock_sd.InputStream.return_value = MagicMock()
        vad_buf = RingBuffer(window_size=8000)
        srmr_buf = RingBuffer(window_size=48000)
        stream = open_stream(vad_buf, srmr_buf, sample_rate=16000)
        mock_sd.InputStream.assert_called_once()
        assert stream is not None

    @patch("acoustic_mirror.audio.capture.sd")
    def test_stream_uses_correct_sample_rate(self, mock_sd):
        mock_sd.InputStream.return_value = MagicMock()
        vad_buf = RingBuffer(window_size=8000)
        srmr_buf = RingBuffer(window_size=48000)
        open_stream(vad_buf, srmr_buf, sample_rate=16000)
        call_kwargs = mock_sd.InputStream.call_args[1]
        assert call_kwargs["samplerate"] == 16000

    @patch("acoustic_mirror.audio.capture.sd")
    def test_stream_is_mono(self, mock_sd):
        mock_sd.InputStream.return_value = MagicMock()
        vad_buf = RingBuffer(window_size=8000)
        srmr_buf = RingBuffer(window_size=48000)
        open_stream(vad_buf, srmr_buf, sample_rate=16000)
        call_kwargs = mock_sd.InputStream.call_args[1]
        assert call_kwargs["channels"] == 1

    @patch("acoustic_mirror.audio.capture.sd")
    def test_callback_writes_to_vad_buffer(self, mock_sd):
        vad_buf = RingBuffer(window_size=8000)
        srmr_buf = RingBuffer(window_size=48000)
        mock_sd.InputStream.return_value = MagicMock()

        open_stream(vad_buf, srmr_buf, sample_rate=16000)
        call_kwargs = mock_sd.InputStream.call_args[1]
        callback = call_kwargs["callback"]

        indata = np.ones((512, 1), dtype=np.float32) * 0.5
        callback(indata, 512, None, None)

        window = vad_buf.get_window()
        assert np.allclose(window[-512:], 0.5)

    @patch("acoustic_mirror.audio.capture.sd")
    def test_callback_writes_to_srmr_buffer(self, mock_sd):
        """Issue #2: the same audio must reach both buffers, not just VAD's."""
        vad_buf = RingBuffer(window_size=8000)
        srmr_buf = RingBuffer(window_size=48000)
        mock_sd.InputStream.return_value = MagicMock()

        open_stream(vad_buf, srmr_buf, sample_rate=16000)
        call_kwargs = mock_sd.InputStream.call_args[1]
        callback = call_kwargs["callback"]

        indata = np.ones((512, 1), dtype=np.float32) * 0.5
        callback(indata, 512, None, None)

        window = srmr_buf.get_window()
        assert np.allclose(window[-512:], 0.5)

    @patch("acoustic_mirror.audio.capture.sd")
    def test_list_devices(self, mock_sd):
        mock_sd.query_devices.return_value = [
            {"name": "Built-in Mic", "max_input_channels": 2},
            {"name": "Speakers", "max_input_channels": 0},
        ]
        mock_sd.default.device = [0, 1]
        result = list_devices()
        assert "Built-in Mic" in result
        assert "Speakers" not in result
