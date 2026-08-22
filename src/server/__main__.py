"""Standalone server entry point: python -m src.server"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="YuGiOhAccess EDOPro-compatible game server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--lobby-port", type=int, default=7933, help="TCP lobby port (default: 7933)")
    parser.add_argument("--http-port", type=int, default=7934, help="HTTP room listing port (default: 7934)")
    parser.add_argument("--ocgcore", default="", help="Path to ocgcore shared library")
    parser.add_argument("--scripts", default="", help="Path to card script directory")
    parser.add_argument("--db", action="append", default=[], help="Path to card database (.cdb), can repeat")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    asyncio.run(run_server(args))


async def run_server(args):
    from server.lobby import LobbyServer
    from server.room_api import RoomAPI
    from server.core import OcgCore

    engine = None
    if args.ocgcore:
        ocgcore_path = Path(args.ocgcore)
        if not ocgcore_path.exists():
            logger.error("ocgcore not found: %s", args.ocgcore)
            sys.exit(1)
        engine = OcgCore(str(ocgcore_path), args.db, args.scripts)
        major, minor = engine.get_version()
        logger.info("ocgcore v%d.%d loaded", major, minor)
    else:
        logger.warning("No ocgcore path specified — duels will not work")

    lobby = LobbyServer(duel_engine=engine)
    await lobby.start(args.host, args.lobby_port)

    api = RoomAPI(lobby)
    await api.start(args.host, args.http_port)

    logger.info("Server ready. Lobby: %s:%d | HTTP: %s:%d",
                args.host, args.lobby_port, args.host, args.http_port)

    try:
        await asyncio.Event().wait()  # run forever
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
        await lobby.stop()
        await api.stop()


if __name__ == "__main__":
    main()
