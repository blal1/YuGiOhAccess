"""Embedded server — runs the game server in-process for offline/local bot duels."""

import asyncio
import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_server_thread: threading.Thread | None = None
_loop: asyncio.AbstractEventLoop | None = None
_lobby = None
_api = None
_engine_status = None


@dataclass
class EngineStatus:
    available: bool = False
    ocgcore_path: str = ""
    script_dir: str = ""
    db_count: int = 0
    version: tuple[int, int] | None = None
    error: str = ""


def start_local_server(lobby_port: int = 7933, http_port: int = 7934,
                       ocgcore_path: str = "", db_paths: list[str] | None = None,
                       script_dir: str = ""):
    """Start embedded server in daemon thread. Idempotent."""
    global _server_thread, _loop
    if _server_thread and _server_thread.is_alive():
        return

    _loop = asyncio.new_event_loop()
    _server_thread = threading.Thread(
        target=_run_server,
        args=(_loop, lobby_port, http_port, ocgcore_path, db_paths or [], script_dir),
        daemon=True,
    )
    _server_thread.start()
    logger.info("Local server starting on ports %d (lobby) / %d (HTTP)", lobby_port, http_port)


def stop_local_server():
    """Graceful shutdown of the embedded server."""
    global _loop, _server_thread, _engine_status, _lobby, _api
    if _loop and _loop.is_running():
        async def _shutdown():
            global _lobby, _api
            if _api:
                await _api.stop()
                _api = None
            if _lobby:
                await _lobby.stop()
                _lobby = None
            _loop.call_soon(_loop.stop)

        future = asyncio.run_coroutine_threadsafe(_shutdown(), _loop)
        try:
            future.result(timeout=5)
        except Exception:
            logger.exception("Local server shutdown failed")
            _loop.call_soon_threadsafe(_loop.stop)
    if _server_thread:
        _server_thread.join(timeout=5)
    _server_thread = None
    _loop = None
    _engine_status = None
    logger.info("Local server stopped")


def is_running() -> bool:
    return _server_thread is not None and _server_thread.is_alive()


def engine_status() -> EngineStatus:
    return _engine_status or EngineStatus()


def _run_server(loop, lobby_port, http_port, ocgcore_path, db_paths, script_dir):
    global _lobby, _api, _engine_status
    asyncio.set_event_loop(loop)

    async def _setup():
        global _lobby, _api, _engine_status
        from server.lobby import LobbyServer
        from server.room_api import RoomAPI
        from server.core import OcgCore
        from server.engine_config import resolve_engine_paths

        engine = None
        paths = resolve_engine_paths(ocgcore_path, db_paths, script_dir)
        _engine_status = EngineStatus(
            available=False,
            ocgcore_path=paths.ocgcore_path,
            script_dir=paths.script_dir,
            db_count=len(paths.db_paths),
        )
        if paths.has_engine:
            try:
                engine = OcgCore(paths.ocgcore_path, paths.db_paths, paths.script_dir)
                major, minor = engine.get_version()
                _engine_status.available = True
                _engine_status.version = (major, minor)
                logger.info("ocgcore loaded: v%d.%d", major, minor)
            except Exception as e:
                _engine_status.error = str(e)
                logger.error("Failed to load ocgcore: %s", e)
        else:
            _engine_status.error = "ocgcore library not found"
            logger.error("ocgcore library not found. Local duels are disabled.")

        _lobby = LobbyServer(duel_engine=engine)
        await _lobby.start("127.0.0.1", lobby_port)

        _api = RoomAPI(_lobby)
        await _api.start("127.0.0.1", http_port)

    loop.run_until_complete(_setup())
    loop.run_forever()
