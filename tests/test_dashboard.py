"""Sprint 9: Dashboard HTTP server and HTML tests."""

import json
import urllib.request

import numpy as np
import pytest

from acoustic_mirror.dashboard.http_server import DashboardServer


class TestHTTPServer:
    def test_serves_index_html(self):
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            url = f"http://localhost:{server.port}/index.html"
            resp = urllib.request.urlopen(url)
            assert resp.status == 200
            html = resp.read().decode()
            assert "Acoustic Speech Monitor" in html
        finally:
            server.stop()

    def test_content_type_is_html(self):
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            url = f"http://localhost:{server.port}/index.html"
            resp = urllib.request.urlopen(url)
            assert "text/html" in resp.headers.get("Content-Type", "")
        finally:
            server.stop()

    def test_static_files_are_revalidated(self):
        """Stale cached pages hid a fix during manual Chrome testing."""
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            resp = urllib.request.urlopen(f"http://localhost:{server.port}/diagnose.html")
            assert resp.headers.get("Cache-Control") == "no-cache"
        finally:
            server.stop()

    def test_config_reports_the_ws_port(self):
        """The page cannot guess the WS port; the server is what knows it."""
        server = DashboardServer(host="localhost", port=0, ws_port=8769)
        server.start()
        try:
            resp = urllib.request.urlopen(f"http://localhost:{server.port}/api/config")
            assert resp.status == 200
            assert "application/json" in resp.headers.get("Content-Type", "")
            assert json.loads(resp.read())["ws_port"] == 8769
        finally:
            server.stop()

    def test_config_reports_null_when_no_ws_port_is_wired(self):
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            resp = urllib.request.urlopen(f"http://localhost:{server.port}/api/config")
            assert json.loads(resp.read())["ws_port"] is None
        finally:
            server.stop()

    def test_404_for_unknown_path(self):
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            url = f"http://localhost:{server.port}/nonexistent"
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(url)
            assert exc_info.value.code == 404
        finally:
            server.stop()


class TestDashboardHTML:
    @pytest.fixture(autouse=True)
    def _load_html(self):
        from pathlib import Path

        html_path = Path(__file__).parent.parent / "src" / "acoustic_mirror" / "dashboard" / "index.html"
        self.html = html_path.read_text()

    def test_html_contains_websocket_connection(self):
        assert "WebSocket" in self.html
        assert "ws://localhost" in self.html

    def test_ws_port_falls_back_to_the_server_config(self):
        """Opening the dashboard without ?ws_port must still connect: the
        8765 literal is only a last resort, not the working default."""
        assert "/api/config" in self.html
        assert "ws_port" in self.html

    def test_html_contains_intelligibility_ring(self):
        assert "ring" in self.html
        assert "<svg" in self.html
        assert "<circle" in self.html

    def test_html_contains_room_profile_card(self):
        assert "rt60" in self.html
        assert "noise-floor" in self.html
        assert "drr" in self.html

    def test_rt60_is_not_drawn_without_confidence(self):
        """ADR-0005 / issue #13: an unmeasured room must not render as a
        0.20s room. Like the other checks in this class this only reads the
        page's source — no test executes this JavaScript (the same gap as
        B4/B6 in the ADR-0004 verification), so it pins that the guard is
        present, not that it works.
        """
        assert "rp.rt60_confidence > 0 ? rp.rt60.toFixed(2) : '--'" in self.html

    def test_html_contains_cause_card(self):
        assert "cause-content" in self.html
        assert "cause-name" in self.html

    def test_html_contains_haptic_preview(self):
        assert "haptic-bars" in self.html


def _wav_bytes(samples, sample_rate=16000, channels=1, sampwidth=2) -> bytes:
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
        if channels > 1:
            pcm = np.repeat(pcm, channels)
        w.writeframes(pcm.tobytes() if sampwidth == 2 else bytes(len(pcm) * sampwidth))
    return buf.getvalue()


class TestDiagnoseEndpoint:
    """POST /api/diagnose (docs/adr/ADR-0004)."""

    @pytest.fixture
    def server(self):
        s = DashboardServer(host="localhost", port=0)
        s.start()
        yield s
        s.stop()

    def _post(self, server, body: bytes):
        req = urllib.request.Request(
            f"http://localhost:{server.port}/api/diagnose",
            data=body,
            headers={"Content-Type": "audio/wav"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=30)

    def _post_error(self, server, body: bytes) -> urllib.error.HTTPError:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            self._post(server, body)
        return exc_info.value

    def test_returns_diagnostic_json(self, server):
        import json

        from tests.synth import reverberant_utterances

        resp = self._post(server, _wav_bytes(reverberant_utterances(0.6, seed=1)))
        assert resp.status == 200
        assert "application/json" in resp.headers["Content-Type"]
        d = json.loads(resp.read())
        assert d["type"] == "diagnostic"
        assert d["rt60"]["value"] is not None

    def test_accepts_48k(self, server):
        import json

        from scipy.signal import resample_poly

        from tests.synth import reverberant_utterances

        y = resample_poly(reverberant_utterances(0.6, seed=1), 3, 1)
        d = json.loads(self._post(server, _wav_bytes(y, sample_rate=48000)).read())
        assert d["duration_seconds"] == pytest.approx(7.0, abs=0.05)
        assert np.isfinite(d["rt60"]["value"])

    def test_rejects_too_short(self, server):
        import json

        err = self._post_error(server, _wav_bytes(np.zeros(16000)))
        assert err.code == 400
        assert "error" in json.loads(err.read())

    def test_rejects_stereo(self, server):
        assert self._post_error(server, _wav_bytes(np.zeros(16000 * 4), channels=2)).code == 400

    def test_rejects_non_16bit(self, server):
        assert self._post_error(server, _wav_bytes(np.zeros(16000 * 4), sampwidth=3)).code == 400

    def test_rejects_garbage(self, server):
        assert self._post_error(server, b"not a wav file").code == 400

    def test_rejects_oversized_body(self, server):
        import http.client

        from acoustic_mirror.dashboard.http_server import MAX_BODY_BYTES

        # Rejected from Content-Length alone, before any body is read —
        # so send only the headers.
        conn = http.client.HTTPConnection("localhost", server.port, timeout=5)
        conn.putrequest("POST", "/api/diagnose")
        conn.putheader("Content-Length", str(MAX_BODY_BYTES + 1))
        conn.endheaders()
        assert conn.getresponse().status == 413
        conn.close()

    def test_rejects_over_30_seconds(self, server):
        assert self._post_error(server, _wav_bytes(np.zeros(16000 * 31))).code == 413

    def test_post_to_other_path_is_404(self, server):
        req = urllib.request.Request(
            f"http://localhost:{server.port}/index.html", data=b"x", method="POST"
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 404

    def test_static_served_while_diagnosing(self, server):
        """ThreadingHTTPServer: a slow diagnose must not block page loads."""
        import threading
        import time

        from tests.synth import reverberant_utterances

        body = _wav_bytes(np.concatenate([reverberant_utterances(0.6, seed=s) for s in (1, 2, 3, 4)]))
        t = threading.Thread(target=lambda: self._post(server, body))
        t.start()
        time.sleep(0.05)
        start = time.monotonic()
        urllib.request.urlopen(f"http://localhost:{server.port}/index.html", timeout=5)
        assert time.monotonic() - start < 0.5
        t.join()


class TestDiagnosePage:
    """dashboard/diagnose.html (docs/adr/ADR-0004)."""

    @pytest.fixture(autouse=True)
    def _load(self):
        from pathlib import Path

        d = Path(__file__).parent.parent / "src" / "acoustic_mirror" / "dashboard"
        self.html = (d / "diagnose.html").read_text()
        self.index = (d / "index.html").read_text()

    def test_served(self):
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            for path in ("diagnose.html", "recorder-worklet.js"):
                assert urllib.request.urlopen(f"http://localhost:{server.port}/{path}").status == 200
        finally:
            server.stop()

    def test_browser_processing_forced_off(self):
        for c in ("echoCancellation: false", "noiseSuppression: false", "autoGainControl: false"):
            assert c in self.html

    def test_records_raw_pcm_not_mediarecorder(self):
        assert "audioWorklet.addModule" in self.html
        assert "MediaRecorder" not in self.html

    def test_lists_microphones(self):
        assert "enumerateDevices" in self.html
        assert "deviceId" in self.html

    def test_posts_wav_to_api(self):
        assert "/api/diagnose" in self.html
        assert "RIFF" in self.html  # WAV encoded client-side

    def test_index_links_to_diagnose(self):
        assert 'href="diagnose.html"' in self.index

    def test_diagnose_links_back(self):
        assert 'href="index.html"' in self.html

    def test_nav_links_carry_the_query_string(self):
        """An explicit ?ws_port= override was dropped when moving between
        the two pages, which showed up as a stuck "\u5207\u65ad" banner."""
        for page in (self.html, self.index):
            assert "location.search" in page

    def test_hidden_attribute_beats_grid_display(self):
        """#results uses class="grid" (display:grid), which overrides the UA
        [hidden] rule unless restated — found by opening the page in Chrome."""
        assert "[hidden] { display: none !important; }" in self.html


class TestBindAndFailure:
    """Promises S5 / S6 (docs/adr/ADR-0004)."""

    def test_default_bind_is_localhost(self):
        import inspect

        assert inspect.signature(DashboardServer.__init__).parameters["host"].default == "localhost"

    def test_socket_is_not_bound_to_every_interface(self):
        server = DashboardServer(port=0)
        server.start()
        try:
            assert server._server.server_address[0] in ("127.0.0.1", "::1")
        finally:
            server.stop()

    def test_analysis_failure_is_500_with_json(self, monkeypatch):
        from acoustic_mirror.dashboard import http_server

        def boom(*args, **kwargs):
            raise RuntimeError("synthetic analysis failure")

        monkeypatch.setattr(http_server, "diagnose", boom)
        server = DashboardServer(host="localhost", port=0)
        server.start()
        try:
            req = urllib.request.Request(
                f"http://localhost:{server.port}/api/diagnose",
                data=_wav_bytes(np.zeros(16000 * 5)),
                headers={"Content-Type": "audio/wav"},
                method="POST",
            )
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(req, timeout=30)
            assert exc_info.value.code == 500
            assert "error" in json.loads(exc_info.value.read())
        finally:
            server.stop()
