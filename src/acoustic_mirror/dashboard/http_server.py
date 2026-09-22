"""HTTP server for the dashboard pages and the batch diagnostic API.

Static files are served from this directory. POST /api/diagnose takes a
mono 16-bit PCM WAV recorded in the browser and returns the batch
diagnostic as JSON (docs/adr/ADR-0004). GET /api/config tells the page
which port the WebSocket broadcaster is on, so the real-time dashboard
connects correctly however it was opened.
"""

import io
import json
import logging
import threading
import wave
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from acoustic_mirror.analysis.batch_diagnostic import MIN_DURATION_SECONDS, diagnose

logger = logging.getLogger(__name__)

_DASHBOARD_DIR = Path(__file__).parent

MAX_DURATION_SECONDS = 30.0
# 30s of 16-bit mono at up to 96kHz, plus header slack. Checked against
# Content-Length before reading, so an oversized upload is never buffered.
MAX_BODY_BYTES = int(MAX_DURATION_SECONDS * 96000 * 2) + 4096


class _BadRequest(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _decode_wav(body: bytes) -> tuple[np.ndarray, int]:
    try:
        with wave.open(io.BytesIO(body), "rb") as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            frames = w.readframes(w.getnframes())
    except (wave.Error, EOFError) as e:
        raise _BadRequest(400, f"not a valid WAV file: {e}") from e
    if channels != 1:
        raise _BadRequest(400, f"expected mono, got {channels} channels")
    if width != 2:
        raise _BadRequest(400, f"expected 16-bit PCM, got {width * 8}-bit")
    samples = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    duration = len(samples) / rate
    if duration < MIN_DURATION_SECONDS:
        raise _BadRequest(400, f"recording is {duration:.1f}s; need at least {MIN_DURATION_SECONDS:.0f}s")
    if duration > MAX_DURATION_SECONDS:
        raise _BadRequest(413, f"recording is {duration:.1f}s; limit is {MAX_DURATION_SECONDS:.0f}s")
    return samples, rate


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, ws_port=None, **kwargs):
        self._ws_port = ws_port
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, format, *args):
        pass  # suppress request logging

    def end_headers(self):
        # Revalidate every load so an updated page isn't masked by the
        # browser's Last-Modified heuristic cache.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/config":
            self._send_json(200, {"ws_port": self._ws_port})
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/diagnose":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            self._send_json(413, {"error": f"body exceeds {MAX_BODY_BYTES} bytes"})
            return
        body = self.rfile.read(length)
        try:
            samples, rate = _decode_wav(body)
            result = diagnose(samples, rate)
        except _BadRequest as e:
            self._send_json(e.status, {"error": str(e)})
            return
        except Exception:
            logger.exception("diagnose failed")
            self._send_json(500, {"error": "analysis failed"})
            return
        self._send_json(200, result.to_dict())


class DashboardServer:
    def __init__(
        self, host: str = "localhost", port: int = 8080, ws_port: int | None = None
    ) -> None:
        self._host = host
        self._port = port
        self._ws_port = ws_port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_address[1]
        return self._port

    def start(self) -> None:
        handler = partial(
            DashboardHandler, directory=_DASHBOARD_DIR, ws_port=self._ws_port
        )
        self._server = ThreadingHTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
