"""Sprint 8: WebSocket broadcast server tests."""

import asyncio
import json

import pytest
import websockets

from acoustic_mirror.feedback.ws_server import WSBroadcaster


@pytest.fixture
async def broadcaster():
    b = WSBroadcaster(host="localhost", port=0)  # port=0 => OS picks free port
    await b.start()
    yield b
    await b.stop()


class TestWSServer:
    @pytest.mark.asyncio
    async def test_server_starts_and_stops(self):
        b = WSBroadcaster(host="localhost", port=0)
        await b.start()
        assert b.port > 0
        await b.stop()

    @pytest.mark.asyncio
    async def test_client_connects(self, broadcaster):
        async with websockets.connect(f"ws://localhost:{broadcaster.port}"):
            # Give server a moment to register the client
            await asyncio.sleep(0.05)
            assert broadcaster.client_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_client(self, broadcaster):
        async with websockets.connect(f"ws://localhost:{broadcaster.port}") as ws:
            await asyncio.sleep(0.05)
            await broadcaster.broadcast({"type": "test", "value": 42})
            msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
            data = json.loads(msg)
            assert data["type"] == "test"
            assert data["value"] == 42

    @pytest.mark.asyncio
    async def test_broadcast_with_no_clients(self, broadcaster):
        # Should not raise
        await broadcaster.broadcast({"type": "test"})

    @pytest.mark.asyncio
    async def test_client_disconnect_handled(self, broadcaster):
        ws = await websockets.connect(f"ws://localhost:{broadcaster.port}")
        await asyncio.sleep(0.05)
        assert broadcaster.client_count == 1
        await ws.close()
        await asyncio.sleep(0.1)
        # After broadcast attempt, disconnected client is cleaned up
        await broadcaster.broadcast({"type": "ping"})
        assert broadcaster.client_count == 0

    @pytest.mark.asyncio
    async def test_multiple_clients(self, broadcaster):
        async with websockets.connect(f"ws://localhost:{broadcaster.port}") as ws1:
            async with websockets.connect(f"ws://localhost:{broadcaster.port}") as ws2:
                await asyncio.sleep(0.05)
                assert broadcaster.client_count == 2
                await broadcaster.broadcast({"type": "multi"})
                msg1 = await asyncio.wait_for(ws1.recv(), timeout=2.0)
                msg2 = await asyncio.wait_for(ws2.recv(), timeout=2.0)
                assert json.loads(msg1)["type"] == "multi"
                assert json.loads(msg2)["type"] == "multi"
