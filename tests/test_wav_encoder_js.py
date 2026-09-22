"""B5 (ADR-0004): the recording page must send 16-bit mono PCM at the audio
context's native rate.

Until now no test executed a line of `diagnose.html`'s JavaScript, so this
promise rested on one manual browser run. The independent verification
recorded it as FAIL three rounds in a row for that reason.

`encodeWav` is a pure function over DataView, so it needs no DOM: Node runs
it, and the server's own `_decode_wav` reads the bytes it produces. That
makes the two halves of the wire format meet in a test. The rest of the page
(getUserMedia, the countdown, the result rendering) still needs a DOM and
stays out of scope here.

Skipped rather than failed when Node is absent, so a machine without it can
still run the suite (cf. issue #11).
"""

import base64
import json
import re
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from acoustic_mirror.dashboard.http_server import _BadRequest, _decode_wav

DIAGNOSE_HTML = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "acoustic_mirror"
    / "dashboard"
    / "diagnose.html"
)

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not installed"
)


def _encode_wav_source() -> str:
    """The page's encodeWav, lifted out of the <script> block verbatim."""
    html = DIAGNOSE_HTML.read_text(encoding="utf-8")
    start = html.index("function encodeWav(")
    end = html.index("\n}\n", start) + len("\n}\n")
    return html[start:end]


def _run_encode_wav(pattern, sample_rate: int, repeat: int = 1, source=None) -> bytes:
    """Run the page's encodeWav under Node and return the bytes it produced.

    `pattern` is tiled `repeat` times inside JS so long recordings do not have
    to travel through argv.
    """
    driver = (
        (source if source is not None else _encode_wav_source())
        + """
// `node -e` puts the first script argument at argv[1], not argv[2].
const pattern = JSON.parse(process.argv[1]);
const rate = Number(process.argv[2]);
const repeat = Number(process.argv[3]);
const samples = new Float32Array(pattern.length * repeat);
for (let r = 0; r < repeat; r++) samples.set(pattern, r * pattern.length);
encodeWav(samples, rate).arrayBuffer().then(b => {
  process.stdout.write(Buffer.from(b).toString('base64'));
});
"""
    )
    out = subprocess.run(
        ["node", "-e", driver, "--", json.dumps(list(pattern)), str(sample_rate), str(repeat)],
        capture_output=True,
        check=True,
        timeout=60,
    )
    return base64.b64decode(out.stdout)


class TestBrowserWavEncoding:
    def test_header_is_16bit_mono_at_the_rate_it_was_given(self):
        """B5. 44100 is used deliberately: it is neither the 48000 a browser
        usually reports nor the 16000 the analysis runs at, so a hard-coded
        rate anywhere in the encoder would show up here."""
        blob = _run_encode_wav([0.0] * 16, 44100)

        with wave.open(__import__("io").BytesIO(blob), "rb") as w:
            assert w.getnchannels() == 1
            assert w.getsampwidth() == 2
            assert w.getframerate() == 44100
            assert w.getnframes() == 16

    def test_samples_survive_the_round_trip(self):
        pattern = [0.0, 0.5, -0.5, 0.25, -0.25, 0.999, -0.999]
        blob = _run_encode_wav(pattern, 48000)

        with wave.open(__import__("io").BytesIO(blob), "rb") as w:
            decoded = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")
        decoded = decoded.astype(np.float32) / 32768.0

        # One LSB of a 16-bit sample, doubled for the asymmetric positive
        # scaling (0x7fff) the encoder uses.
        assert np.allclose(decoded, pattern, atol=2 / 32768)

    def test_out_of_range_samples_clip_instead_of_wrapping(self):
        """Without the Math.max/min clamp, setInt16 wraps: +1.5 would come
        back as a large negative number, which reads as a loud click the
        analysis would treat as signal."""
        blob = _run_encode_wav([1.5, -1.5, 1.0, -1.0], 48000)

        with wave.open(__import__("io").BytesIO(blob), "rb") as w:
            decoded = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2")

        assert decoded[0] == 32767
        assert decoded[1] == -32768
        assert decoded[2] == 32767
        assert decoded[3] == -32768

    def test_the_server_accepts_what_the_page_produces(self):
        """The wire format's two halves meet here: bytes written by the
        page's encoder, read by the endpoint's own decoder."""
        rate = 48000
        pattern = list(np.sin(np.linspace(0, 2 * np.pi, 480)).astype(float))
        blob = _run_encode_wav(pattern, rate, repeat=350)  # 3.5s

        samples, decoded_rate = _decode_wav(blob)

        assert decoded_rate == rate  # native rate preserved, not resampled here
        assert len(samples) == 480 * 350
        assert samples.dtype == np.float32

    def test_this_test_can_see_a_broken_encoder(self):
        """Guards the harness itself: if the extraction or the Node run were
        silently doing nothing, every assertion above would pass on a
        malformed file too. Stereo is the one defect the server rejects by
        name, so it is the cheapest thing to fake."""
        broken = _encode_wav_source().replace(
            "view.setUint16(22, 1, true);", "view.setUint16(22, 2, true);"
        )
        assert "setUint16(22, 2" in broken, "the mono field moved; update this test"

        blob = _run_encode_wav([0.0] * 480, 48000, repeat=350, source=broken)

        with pytest.raises(_BadRequest, match="expected mono"):
            _decode_wav(blob)
