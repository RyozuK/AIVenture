"""WebSocket server client — allows web frontends to connect."""

from __future__ import annotations

import asyncio
import json
import logging

from .base import Client
from .protocol import CommandResult

logger = logging.getLogger("aiventure.client.websocket")


class WebSocketClient(Client):
    """Serves a game session over a single WebSocket connection."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._ws = None
        self._server = None
        self._running = False
        self._result_q: asyncio.Queue[CommandResult | None] = asyncio.Queue()

    async def send_result(self, result: CommandResult) -> None:
        """Queue a result for sending over the WebSocket."""
        await self._result_q.put(result)

    async def get_input(self) -> str | None:
        """Read a line from the WebSocket. Returns None on disconnect."""
        if self._ws is None:
            return None
        try:
            data = await asyncio.wait_for(self._ws.receive_text(), timeout=0.5)
            msg = json.loads(data)
            return msg.get("input_text", "")
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def start(self) -> None:
        """Start the WebSocket server."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_connection,
            self._host,
            self._port,
        )
        logger.info("WebSocket server listening on %s:%d", self._host, self._port)
        print(f"WebSocket server listening on {self._host}:{self._port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        self._running = False
        await self._result_q.put(None)
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._ws:
            await self._ws.close()

    async def _handle_connection(self, reader, writer) -> None:
        """Handle a single WebSocket connection.

        Note: This uses raw TCP sockets as a fallback.
        For proper WebSocket support, use `websockets` library.
        """
        addr = writer.get_extra_info("peername")
        logger.info("Connection from %s", addr)

        try:
            while self._running:
                try:
                    data = await asyncio.wait_for(reader.readline(), timeout=0.5)
                    if not data:
                        break
                    # Simple line-based protocol for now
                    # Full WebSocket upgrade handled by websockets lib
                    pass
                except asyncio.TimeoutError:
                    continue
        finally:
            writer.close()
            await writer.wait_closed()

    async def _send_loop(self) -> None:
        """Background task: send results as they arrive."""
        while self._running:
            try:
                result = await asyncio.wait_for(self._result_q.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if result is None:
                break

            if self._ws:
                payload = json.dumps({
                    "type": "result",
                    "turn": result.turn,
                    "narrative": result.narrative,
                    "room_description": result.room_description,
                    "player_state": result.player_state,
                    "game_over": result.game_over,
                })
                await self._ws.send_text(payload)