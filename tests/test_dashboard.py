"""Sprint 9: Dashboard HTTP server and HTML tests."""

import urllib.request

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

    def test_html_contains_intelligibility_ring(self):
        assert "ring" in self.html
        assert "<svg" in self.html
        assert "<circle" in self.html

    def test_html_contains_room_profile_card(self):
        assert "rt60" in self.html
        assert "noise-floor" in self.html
        assert "drr" in self.html

    def test_html_contains_cause_card(self):
        assert "cause-content" in self.html
        assert "cause-name" in self.html

    def test_html_contains_haptic_preview(self):
        assert "haptic-bars" in self.html
