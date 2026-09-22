"""Every bot deck the build can pilot must reach the player, online and off.

Three things have to agree or the player gets a bot that is not the one they
chose: the executors compiled into WindBot, the deck files it loads them with,
and the names the menu shows. These pin all three together, and pin down the
inputs the bot is launched with, which are the same for a local room and for a
room on someone else's server.
"""

import json
import pathlib
import re

import pytest

from bot import deck_catalogue

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECKS_DIR = ROOT / "src" / "data" / "bot" / "Decks"
EXECUTOR_DIR = ROOT / "Game" / "AI" / "Decks"
BOTS_JSON = ROOT / "src" / "data" / "bot" / "bots.json"

# These exist to exercise the engine, not to be played; they ship without a deck.
DEVELOPMENT_EXECUTORS = {"Test", "Lucky"}


def executors():
    """Deck key -> deck file, from the executors' own [Deck] attributes."""
    found = {}
    for source in EXECUTOR_DIR.glob("*.cs"):
        text = source.read_text(encoding="utf-8", errors="replace")
        for key, deck_file in re.findall(r'\[Deck\("([^"]+)",\s*"([^"]+)"', text):
            found[key] = deck_file
    return found


@pytest.fixture(scope="module")
def registered():
    found = executors()
    assert found, "no WindBot executors found; is the source tree complete?"
    return found


def test_every_playable_executor_is_offered(registered):
    playable = {
        key: deck_file for key, deck_file in registered.items()
        if key not in DEVELOPMENT_EXECUTORS and (DECKS_DIR / f"{deck_file}.ydk").exists()
    }
    missing = sorted(set(playable) - set(deck_catalogue.KEY_TO_DECK_FILE))
    assert not missing, f"executors the menu never offers: {missing}"


def test_every_offered_deck_has_its_file():
    missing = [
        f"{key} -> {deck_file}.ydk"
        for key, deck_file in deck_catalogue.KEY_TO_DECK_FILE.items()
        if not (DECKS_DIR / f"{deck_file}.ydk").exists()
    ]
    assert not missing, f"offered decks with no deck file: {missing}"


def test_every_offered_deck_has_an_executor(registered):
    unknown = sorted(set(deck_catalogue.KEY_TO_DECK_FILE) - set(registered))
    assert not unknown, f"offered decks WindBot cannot resolve: {unknown}"


def test_every_offered_deck_has_a_name_for_the_player():
    entries = {entry["deck"] for entry in json.loads(BOTS_JSON.read_text(encoding="utf-8"))}
    nameless = sorted(set(deck_catalogue.KEY_TO_DECK_FILE) - entries)
    assert not nameless, f"offered decks missing from bots.json: {nameless}"


def test_no_deck_file_is_left_stranded(registered):
    used = {f"{deck_file}.ydk" for deck_file in registered.values()}
    stranded = sorted(p.name for p in DECKS_DIR.glob("*.ydk") if p.name not in used)
    assert not stranded, f"deck files no executor claims: {stranded}"


def test_the_deck_files_are_not_empty():
    empty = []
    for deck_file in sorted(set(deck_catalogue.KEY_TO_DECK_FILE.values())):
        text = (DECKS_DIR / f"{deck_file}.ydk").read_text(encoding="utf-8", errors="replace")
        if not [line for line in text.splitlines() if line.strip().isdigit()]:
            empty.append(deck_file)
    assert not empty, f"deck files with no cards: {empty}"


def test_the_deck_key_survives_whatever_the_menu_passes():
    from bot.launcher import _deck_file_name_to_windbot_key

    for key, deck_file in deck_catalogue.KEY_TO_DECK_FILE.items():
        assert _deck_file_name_to_windbot_key(key) == key
        assert _deck_file_name_to_windbot_key(deck_file) == key
        assert _deck_file_name_to_windbot_key(f"{deck_file}.ydk") == key


# --------------------------------------------------- what the bot is given --

def test_the_bot_is_given_every_card_database(tmp_path, mocker):
    from bot import launcher
    from core import variables

    content = tmp_path / "sync" / "databases2" / "content"
    content.mkdir(parents=True)
    for name in ("cards.cdb", "cards-rush.cdb", "prerelease-others.cdb"):
        (content / name).write_bytes(b"")
    mocker.patch.object(variables, "APP_DATA_DIR", str(tmp_path))
    mocker.patch.object(variables, "LOCAL_DATA_DIR", None)

    found = launcher._find_bot_database_paths()

    assert len(found) == 3
    assert any(path.endswith("cards.cdb") for path in found)


def test_a_directory_without_the_main_database_is_skipped(tmp_path, mocker):
    from bot import launcher
    from core import variables

    empty = tmp_path / "sync" / "databases2" / "content"
    empty.mkdir(parents=True)
    (empty / "cards-rush.cdb").write_bytes(b"")
    fallback = tmp_path / "data" / "databases"
    fallback.mkdir(parents=True)
    (fallback / "cards.cdb").write_bytes(b"")
    mocker.patch.object(variables, "APP_DATA_DIR", str(tmp_path))
    mocker.patch.object(variables, "LOCAL_DATA_DIR", str(tmp_path / "data"))

    found = launcher._find_bot_database_paths()

    assert len(found) == 1
    assert found[0].endswith("cards.cdb")


def test_the_launch_payload_is_all_strings(mocker):
    """WindBot deserialises every field as a string; a number loses the lot."""
    from bot import engine

    mocker.patch.object(engine, "_bot_initialized", True)
    sent = {}

    class FakeWindBot:
        @staticmethod
        def RunAndroid(payload):
            sent["payload"] = payload

    mocker.patch.dict("sys.modules", {"WindBot": mocker.MagicMock(WindBot=FakeWindBot)})

    engine.launch_bot("127.0.0.1", 7911, room_info=131109985, deck="Horus", debug=False)

    payload = json.loads(sent["payload"])
    assert payload["HostInfo"] == "131109985"
    assert all(isinstance(value, str) for value in payload.values())


def test_the_bot_is_launched_at_whatever_server_the_room_is_on(mocker):
    """A room on someone else's server must be reached the same way."""
    from bot import launcher

    launched = {}
    mocker.patch.object(launcher, "_ensure_engine")
    engine = mocker.patch("bot.engine.launch_bot",
                          side_effect=lambda **kwargs: launched.update(kwargs))
    mocker.patch.dict("sys.modules", {"bot.engine": mocker.MagicMock(launch_bot=engine)})
    from core.dotdict import DotDict

    client = mocker.MagicMock()
    client.server.address = "duel.example.org"
    client.server.lobby_port = 7911
    client.room.roomid = 4242
    client.memory = DotDict()

    launcher.launch_bot_for_room(client, deck="Horus")

    assert launched["host"] == "duel.example.org"
    assert launched["port"] == 7911
    assert launched["room_info"] == "4242"
    assert launched["deck"] == "Horus"


def test_a_protected_room_is_joined_with_its_password(mocker):
    from bot import launcher
    from core.dotdict import DotDict

    client = mocker.MagicMock()
    client.memory = DotDict(room_password="hunter2")
    client.room.roomid = 4242

    assert launcher._room_join_token(client) == "hunter2"


def test_an_open_room_is_joined_by_its_id(mocker):
    from bot import launcher
    from core.dotdict import DotDict

    client = mocker.MagicMock()
    client.memory = DotDict()
    client.room.roomid = 4242

    assert launcher._room_join_token(client) == "4242"


def test_an_empty_password_falls_back_to_the_id(mocker):
    from bot import launcher
    from core.dotdict import DotDict

    client = mocker.MagicMock()
    client.memory = DotDict(room_password="")
    client.room.roomid = 7

    assert launcher._room_join_token(client) == "7"


# ------------------------------------ the join packet the bot actually sends --

def _windbot_join_packet(token):
    """CTOS_JoinGame as WindBot builds it: the token goes in the password."""
    import ctypes

    from game.edo import structs, structs_utils

    join = structs.JoinGame()
    join.password = structs_utils.string_to_u16(token, structs_utils.PASS_NAME_MAX_LENGTH)
    return bytes(join)[:ctypes.sizeof(structs.JoinGame)]


def _room(server, password=""):
    from server.lobby import Room

    room = Room(131109985, {"password": password})
    room.password = password
    server.rooms[room.room_id] = room
    return room


def _connection(mocker):
    from server.lobby import PlayerConnection

    conn = PlayerConnection.__new__(PlayerConnection)
    conn.name = "WindBot"
    conn.slot = -1
    conn.ready = False
    conn.room = None
    conn.deck_main = conn.deck_extra = conn.deck_side = []
    conn._closed = False
    conn.send = mocker.AsyncMock()
    conn.writer = mocker.MagicMock()
    return conn


def test_the_bot_joins_an_open_room_by_its_id(mocker):
    import asyncio

    from server.lobby import LobbyServer

    server = LobbyServer()
    room = _room(server)
    conn = _connection(mocker)

    asyncio.run(server._handle_join_game(conn, _windbot_join_packet(str(room.room_id))))

    assert conn.room is room
    assert room.players[0] is conn


def test_the_bot_joins_a_protected_room_with_the_password(mocker):
    import asyncio

    from server.lobby import LobbyServer

    server = LobbyServer()
    room = _room(server, password="hunter2")
    conn = _connection(mocker)

    asyncio.run(server._handle_join_game(conn, _windbot_join_packet("hunter2")))

    assert conn.room is room


def test_a_wrong_password_keeps_the_bot_out(mocker):
    import asyncio

    from server.lobby import LobbyServer

    server = LobbyServer()
    _room(server, password="hunter2")
    conn = _connection(mocker)

    asyncio.run(server._handle_join_game(conn, _windbot_join_packet("wrong")))

    assert conn.room is None
