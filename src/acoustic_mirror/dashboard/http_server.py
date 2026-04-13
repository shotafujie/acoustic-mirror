"""Simple HTTP server to serve the dashboard HTML."""

import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

_DASHBOARD_DIR = Path(__file__).parent


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(directory), **kwargs)

    def log_message(self, format, *args):
        pass  # suppress request logging


class DashboardServer:
    def __init__(self, host: str = "localhost", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is not None:
            return self._server.server_address[1]
        return self._port

    def start(self) -> None:
        handler = partial(DashboardHandler, directory=_DASHBOARD_DIR)
        self._server = HTTPServer((self._host, self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None
