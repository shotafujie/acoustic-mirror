"""WebSocket broadcast server for real-time analysis results.

Sends JSON messages to all connected dashboard clients.
"""

import asyncio
import json
import logging

import websockets
from websockets.asyncio.server import ServerConnection

logger = logging.getLogger(__name__)


class WSBroadcaster:
    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._clients: set[ServerConnection] = set()
        self._server = None

    @property
    def port(self) -> int:
        if self._server is not None:
            for sock in self._server.sockets:
                return sock.getsockname()[1]
        return self._port

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def _handler(self, websocket: ServerConnection) -> None:
        self._clients.add(websocket)
        try:
            async for _ in websocket:
                pass  # We don't expect messages from clients
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)

    async def start(self) -> None:
        self._server = await websockets.serve(
            self._handler, self._host, self._port
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def broadcast(self, message: dict) -> None:
        if not self._clients:
            return
        data = json.dumps(message)
        disconnected = set()
        for client in self._clients.copy():
            try:
                await client.send(data)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        self._clients -= disconnected
