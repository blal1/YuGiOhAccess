import logging
import pathlib

from bot import deck_catalogue
from core import variables

logger = logging.getLogger(__name__)

_engine_ready = False


def bot_asset_path() -> pathlib.Path | None:
    """The WindBot asset directory, or None when the bot has not been built.

    WindBot reads its decks, dialogs and bots.json from here (Program.AssetPath),
    not from the repository. Anything that offers the player a bot deck has to
    look in this directory, or it will offer decks the bot cannot load.
    """
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
    return None


def bot_decks_path() -> pathlib.Path | None:
    """Where WindBot looks for .ydk files: <asset path>/Decks (see Game/AI/Deck.cs)."""
    asset_path = bot_asset_path()
    if asset_path is None:
        return None
    decks = asset_path / "Decks"
    return decks if decks.exists() else None


def _find_bot_asset_path() -> pathlib.Path:
    """Same as bot_asset_path, but refuses to continue when the bot is missing."""
    asset_path = bot_asset_path()
    if asset_path is None:
        raise FileNotFoundError(
            "WindBot.Desktop.dll was not found. Run scripts/build_windbot.py before adding a bot."
        )
    return asset_path


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
    """Every card database the bot should know about.

    The duel engine loads all of them, so handing the bot only cards.cdb left
    it blind to everything in the other files: it cannot make a decision about
    a card it has never heard of, and it would simply pass instead.
    """
    candidates = [
        pathlib.Path(variables.APP_DATA_DIR) / "sync" / "databases2" / "content",
    ]
    if variables.LOCAL_DATA_DIR:
        candidates.append(pathlib.Path(variables.LOCAL_DATA_DIR) / "databases")
    for path in candidates:
        path = path.resolve()
        if not path.exists():
            continue
        databases = sorted(path.glob("*.cdb"))
        if not any(db.name == "cards.cdb" for db in databases):
            # Without the main database the rest is not worth loading.
            continue
        logger.debug("Bot card databases from %s: %d file(s)", path, len(databases))
        return [str(db.resolve()) for db in databases]
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
    """Resolve whatever the UI passed to the key DecksManager looks up.

    Accepts the key itself or the deck file name. The map comes from the
    executors' own [Deck] attributes; the old four entry table plus an "AI_"
    strip got most of the catalogue wrong, and a key WindBot cannot resolve
    makes it load a random deck instead of the chosen one.
    """
    deck = (deck or "").strip()
    if not deck:
        return ""
    if deck in deck_catalogue.KEY_TO_DECK_FILE:
        return deck
    stem = pathlib.Path(deck).stem
    if stem in deck_catalogue.KEY_TO_DECK_FILE:
        return stem
    resolved = deck_catalogue.DECK_FILE_TO_KEY.get(stem)
    if resolved:
        return resolved
    logger.warning("Unknown bot deck %r; WindBot will pick one at random", deck)
    if stem.startswith("AI_"):
        return stem[3:]
    return stem


def _room_join_token(client) -> str:
    """What the bot must present to get into this room.

    WindBot puts this in the password field of its join packet. A public server
    only lets it into a protected room with the real password, so that wins when
    there is one; otherwise the room id, which is what an open room expects.
    """
    memory = getattr(client, "memory", None)
    password = getattr(memory, "room_password", "") if memory else ""
    if password:
        return str(password)
    return str(client.room.roomid)


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

    # The setting is the master switch and the caller can only be stricter.
    # Consulting the setting only when the caller had already said no meant
    # every normal call kept the default of True, and unticking "Enable bot
    # chatter during duels" changed nothing at all.
    chat = bool(chat) and bool(variables.config.get("enable_bot_chat", True))

    engine.launch_bot(
        host=client.server.address,
        port=client.server.lobby_port,
        room_info=_room_join_token(client),
        deck=_deck_file_name_to_windbot_key(deck),
        name="WindBot",
        hand=hand,
        chat=chat,
        version=_edo_client_version_to_int(variables.edo_client_version),
    )
