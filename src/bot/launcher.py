import logging
import pathlib

from core import variables

logger = logging.getLogger(__name__)

_engine_ready = False
_DECK_FILE_TO_WINDBOT_KEY = {
    "AI_Blackwing": "Blackwing",
    "AI_BlueEyes": "Blue-Eyes",
    "AI_DarkMagician": "DarkMagician",
    "AI_Dragun": "Dragun",
}


def _find_bot_asset_path() -> pathlib.Path:
    """Return the first local WindBot asset directory containing the embedded DLL."""
    candidates = [
        pathlib.Path(variables.EXECUTABLE_DIR) / "data" / "bot",
        pathlib.Path(variables.EXECUTABLE_DIR).parent / "src" / "data" / "bot",
        pathlib.Path(variables.EXECUTABLE_DIR).parent / "data" / "bot",
    ]
    if variables.LOCAL_DATA_DIR:
        candidates.insert(0, pathlib.Path(variables.LOCAL_DATA_DIR) / "bot")
    for path in candidates:
        path = path.resolve()
        if (path / "WindBot.Desktop.dll").exists():
            return path
    raise FileNotFoundError(
        "WindBot.Desktop.dll was not found. Run scripts/build_windbot.py before adding a bot."
    )


def _ensure_engine():
    """Lazy-init the bot engine on first use."""
    global _engine_ready
    if _engine_ready:
        return
    from bot import engine

    asset_path = _find_bot_asset_path()
    db_paths = _find_bot_database_paths()

    engine.init_bot(str(asset_path), db_paths)
    _engine_ready = True


def _find_bot_database_paths() -> list[str]:
    candidates = [
        pathlib.Path(variables.APP_DATA_DIR) / "sync" / "databases2" / "content",
    ]
    if variables.LOCAL_DATA_DIR:
        candidates.append(pathlib.Path(variables.LOCAL_DATA_DIR) / "databases")
    for path in candidates:
        path = path.resolve()
        if path.exists():
            primary_db = path / "cards.cdb"
            if primary_db.exists():
                return [str(primary_db.resolve())]
    return []


def _edo_client_version_to_int(version) -> int:
    try:
        return (
            int(version.client[0])
            | (int(version.client[1]) << 8)
            | (int(version.core[0]) << 16)
            | (int(version.core[1]) << 24)
        )
    except (AttributeError, IndexError, TypeError, ValueError):
        return int(version)


def _deck_file_name_to_windbot_key(deck: str) -> str:
    deck = (deck or "").strip()
    if not deck:
        return ""
    deck = pathlib.Path(deck).stem
    if deck in _DECK_FILE_TO_WINDBOT_KEY:
        return _DECK_FILE_TO_WINDBOT_KEY[deck]
    if deck.startswith("AI_"):
        return deck[3:]
    return deck


def launch_bot_for_room(client, deck: str = "", hand: int = 0, chat: bool = True):
    """Launch an embedded bot targeting the current room on the current server.

    Works with any server — ProjectIgnis (multiplayer) or localhost (offline).
    The bot connects via TCP to whatever server the player's room is on.
    """
    _ensure_engine()
    from bot import engine

    rock_paper_scissors_bot_behavior = variables.config.get("rock_paper_scissors_bot_behavior")
    if hand == 0:
        if rock_paper_scissors_bot_behavior == "rock":
            hand = 2
        elif rock_paper_scissors_bot_behavior == "paper":
            hand = 3
        elif rock_paper_scissors_bot_behavior == "scissors":
            hand = 1

    if not chat:
        chat = variables.config.get("enable_bot_chat", True)

    engine.launch_bot(
        host=client.server.address,
        port=client.server.lobby_port,
        room_info=client.room.roomid,
        deck=_deck_file_name_to_windbot_key(deck),
        name="WindBot",
        hand=hand,
        chat=chat,
        version=_edo_client_version_to_int(variables.edo_client_version),
    )
