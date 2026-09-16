"""Microphone capture using sounddevice.

Follows the same pattern as koenami/audio.py — a thin wrapper around
sd.InputStream that bridges the audio callback to a RingBuffer.
"""

import sounddevice as sd

from acoustic_mirror.audio.buffer import RingBuffer


def list_devices() -> str:
    """Return a formatted string of available audio input devices."""
    devices = sd.query_devices()
    lines = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = " *" if i == sd.default.device[0] else ""
            lines.append(f"  [{i}] {dev['name']} (ch={dev['max_input_channels']}){marker}")
    if not lines:
        return "No input devices found."
    return "Available input devices (* = default):\n" + "\n".join(lines)


def open_stream(
    vad_buffer: RingBuffer,
    srmr_buffer: RingBuffer,
    device: int | None = None,
    sample_rate: int = 16000,
    block_size: int = 512,
) -> sd.InputStream:
    """Open a sounddevice InputStream that fans audio out to both ring buffers.

    Two buffers (not one shared window) because VAD/RT60/DRR need a short,
    responsive window while SRMR needs several seconds of context — see
    docs/adr/ADR-0002. Named explicitly rather than a `Sequence[RingBuffer]`
    so each buffer's purpose is visible at the call site.
    """

    def _callback(indata, frames, time_info, status):
        if status:
            pass  # drop overflows silently
        data = indata[:, 0].copy()
        vad_buffer.write(data)
        srmr_buffer.write(data)

    stream = sd.InputStream(
        device=device,
        channels=1,
        samplerate=sample_rate,
        blocksize=block_size,
        dtype="float32",
        callback=_callback,
    )
    return stream
