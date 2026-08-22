"""HTTP room listing API — compatible with ProjectIgnis room listing format."""

import json
import logging
from aiohttp import web

logger = logging.getLogger(__name__)


class RoomAPI:
    """Lightweight HTTP server that serves room listings."""

    def __init__(self, lobby):
        self.lobby = lobby
        self._app = web.Application()
        self._app.router.add_get("/", self._handle_room_list)
        self._app.router.add_get("/api/getrooms", self._handle_room_list)
        self._runner: web.AppRunner | None = None

    async def start(self, host: str = "0.0.0.0", port: int = 7934):
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, host, port)
        await site.start()
        logger.info("Room API listening on %s:%d", host, port)

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()

    async def _handle_room_list(self, request: web.Request) -> web.Response:
        rooms = [room.to_json() for room in self.lobby.rooms.values()]
        return web.json_response({"rooms": rooms}, dumps=_json_dumps)


def _json_default(value):
    if isinstance(value, bytes):
        return list(value)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _json_dumps(data):
    return json.dumps(data, default=_json_default)
