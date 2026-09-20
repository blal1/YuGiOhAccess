"""Tests for the lobby protocol surface, checked against the EDOPro client.

The reference client is cloned into build/refs by hand; when it is not there the
comparison tests skip and only the behavioural ones run.
"""

import re
import struct
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REFERENCE = Path(__file__).resolve().parent.parent / "build" / "refs" / "edopro-client" / "gframe" / "network.h"


def _reference_defines(prefix):
    if not REFERENCE.exists():
        pytest.skip("the EDOPro reference client is not cloned into build/refs")
    header = REFERENCE.read_text(encoding="utf-8", errors="replace")
    return {
        match.group(1): int(match.group(2), 0)
        for match in re.finditer(rf"^#define\s+({prefix}_[A-Z0-9_]+)\s+(0x[0-9a-fA-F]+|\d+)", header, re.M)
    }


def _ours(cls):
    return {name: value for name, value in vars(cls).items()
            if not name.startswith("_") and isinstance(value, int)}


def test_every_client_to_server_packet_is_declared():
    from game.edo import structs

    reference = _reference_defines("CTOS")
    ours = set(_ours(structs.ClientIdType).values())
    missing = sorted(name for name, value in reference.items() if value not in ours)
    assert missing == [], f"not declared in structs.ClientIdType: {missing}"


def test_every_server_to_client_packet_is_declared_and_handled():
    import ui  # noqa: F401  (importing registers the handlers)
    from core import utils
    from game.edo import structs

    reference = _reference_defines("STOC")
    declared = set(_ours(structs.ServerIdType).values())
    handled = {int(packet_id) for packet_id in utils.packet_handlers if packet_id != -1}

    undeclared = sorted(name for name, value in reference.items() if value not in declared)
    assert undeclared == [], f"not declared in structs.ServerIdType: {undeclared}"

    unhandled = sorted(name for name, value in reference.items() if value not in handled)
    assert unhandled == [], f"declared but with no packet handler: {unhandled}"


def test_the_ids_we_share_with_edopro_have_the_same_values():
    from game.edo import structs

    for prefix, cls, renames in (
        ("CTOS", structs.ClientIdType, {
            "CTOS_HAND_RESULT": "RPS_CHOICE", "CTOS_TP_RESULT": "TURN_CHOICE",
            "CTOS_HS_TODUELIST": "TO_DUELIST", "CTOS_HS_TOOBSERVER": "TO_OBSERVER",
            "CTOS_HS_READY": "READY", "CTOS_HS_NOTREADY": "NOT_READY",
            "CTOS_HS_KICK": "TRY_KICK", "CTOS_HS_START": "TRY_START",
            "CTOS_REMATCH_RESPONSE": "REMATCH",
        }),
        ("STOC", structs.ServerIdType, {
            "STOC_SELECT_HAND": "CHOOSE_RPS", "STOC_SELECT_TP": "CHOOSE_ORDER",
            "STOC_HAND_RESULT": "RPS_RESULT", "STOC_TP_RESULT": "ORDER_RESULT",
            "STOC_HS_PLAYER_ENTER": "PLAYER_ENTER", "STOC_HS_PLAYER_CHANGE": "PLAYER_CHANGE",
            "STOC_HS_WATCH_CHANGE": "WATCH_CHANGE", "STOC_WAITING_REMATCH": "REMATCH_WAIT",
        }),
    ):
        ours = _ours(cls)
        for name, value in _reference_defines(prefix).items():
            our_name = renames.get(name, name.split("_", 1)[1])
            if our_name in ours:
                assert ours[our_name] == value, f"{name} is 0x{value:02x} upstream, 0x{ours[our_name]:02x} here"


# --------------------------------------------------------------- legacy chat

def test_legacy_chat_packet_is_read(mocker):
    import ui
    from core import utils

    mocker.patch("core.utils.output")
    client = MagicMock()
    client.room.users = [{"name": "Kaiba", "pos": 0}, {"name": "Yugi", "pos": 1}]
    client.memory = MagicMock()
    client.memory.chat_history = []

    message = "your move".encode("utf-16-le")
    payload = struct.pack("<H", 1) + message
    ui.handle_chat(client, payload, len(payload))

    said = [call.args[0] for call in utils.output.call_args_list]
    assert "Yugi: your move" in said


def test_legacy_chat_falls_back_to_a_seat_number(mocker):
    import ui
    from core import utils

    mocker.patch("core.utils.output")
    client = MagicMock()
    client.room.users = []
    client.memory = MagicMock()
    client.memory.chat_history = []

    payload = struct.pack("<H", 8) + "hello".encode("utf-16-le")
    ui.handle_chat(client, payload, len(payload))

    assert any("Observer: hello" in call.args[0] for call in utils.output.call_args_list)


def test_legacy_chat_ignores_a_short_packet(mocker):
    import ui
    from core import utils

    mocker.patch("core.utils.output")
    ui.handle_chat(MagicMock(), b"\x01", 1)
    utils.output.assert_not_called()


# ------------------------------------------------------------ time confirming

def test_time_limit_is_confirmed_to_the_server(mocker):
    from game.edo import structs
    from ui import duel_field

    client = MagicMock()
    client.what_player_am_i = 0
    client.player = MagicMock()
    payload = bytes(structs.StocTimeLimit(team=0, time=180))

    duel_field.handle_time_limit_announcement(client, payload, len(payload))

    # Without this the server keeps counting our clock down on its own estimate.
    client.send.assert_called_once_with(structs.ClientIdType.TIME_CONFIRM)
    assert client.player.turn_timer == 180


def test_the_opponents_time_limit_is_not_confirmed(mocker):
    from game.edo import structs
    from ui import duel_field

    client = MagicMock()
    client.what_player_am_i = 0
    payload = bytes(structs.StocTimeLimit(team=1, time=180))

    duel_field.handle_time_limit_announcement(client, payload, len(payload))
    client.send.assert_not_called()


def test_time_confirm_is_sent_even_before_the_player_object_exists(mocker):
    from game.edo import structs
    from ui import duel_field

    client = MagicMock()
    client.what_player_am_i = 0
    client.player = None
    payload = bytes(structs.StocTimeLimit(team=0, time=180))

    duel_field.handle_time_limit_announcement(client, payload, len(payload))
    client.send.assert_called_once_with(structs.ClientIdType.TIME_CONFIRM)


# --------------------------------------------------------------- room actions

def test_taking_the_ready_flag_back(mocker):
    from game.edo import structs
    from ui import room_ui

    mocker.patch("ui.room_ui.display_room_menu")
    mocker.patch("ui.room_ui.utils.output")
    client = MagicMock()
    client.memory.is_ready = True

    room_ui.handle_room_menu_not_ready(client)

    client.send.assert_called_once_with(structs.ClientIdType.NOT_READY)
    assert client.memory.is_ready is False


def test_readying_records_that_we_are_ready(mocker):
    from game.edo import structs
    from ui import room_ui

    client = MagicMock()
    client.memory.is_host = False
    room_ui.handle_room_menu_ready_or_start(client)

    assert client.memory.is_ready is True
    client.send.assert_any_call(structs.ClientIdType.READY)


def test_the_host_can_remove_a_player(mocker):
    from game.edo import structs
    from ui import room_ui

    mocker.patch("ui.room_ui.display_room_menu")
    mocker.patch("ui.room_ui.utils.output")
    client = MagicMock()

    room_ui.send_kick(client, 1, "Yugi")

    packet_id, payload = client.send.call_args.args
    assert packet_id == structs.ClientIdType.TRY_KICK
    assert isinstance(payload, structs.CtosKick)
    assert payload.pos == 1


# ------------------------------------------------- WindBot's own bot catalogue

def test_bots_json_is_valid_json():
    """WindBot ships strict JSON upstream; a trailing comma broke reading it here."""
    import json

    path = Path(__file__).resolve().parent.parent / "bots.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    assert entries and all("name" in entry and "deck" in entry for entry in entries)


def test_bot_menu_uses_the_names_and_difficulties_from_bots_json(mocker):
    from ui import room_ui

    mocker.patch("ui.room_ui._load_bot_catalogue", return_value=[
        {"name": "Dark Magician", "deck": "DarkMagician", "difficulty": 3},
        {"name": "Blue-Eyes", "deck": "Blue-Eyes", "difficulty": 2},
    ])

    choices = room_ui._bot_choices(["DarkMagician", "Blue-Eyes"])

    # Sorted by what is read out, not by the order the decks happened to arrive.
    assert choices == [
        ("Blue-Eyes, difficulty 2", "Blue-Eyes"),
        ("Dark Magician, difficulty 3", "DarkMagician"),
    ]


def test_a_deck_the_catalogue_does_not_mention_is_still_offered(mocker):
    from ui import room_ui

    mocker.patch("ui.room_ui._load_bot_catalogue", return_value=[])
    assert room_ui._bot_choices(["Blackwing"]) == [("Blackwing", "Blackwing")]


def test_an_unreadable_catalogue_falls_back_to_the_deck_keys(mocker, tmp_path):
    from ui import room_ui

    mocker.patch("ui.room_ui._install_root", return_value=tmp_path)
    assert room_ui._load_bot_catalogue() == []
    assert room_ui._bot_choices(["Dragun"]) == [("Dragun", "Dragun")]


def test_only_decks_with_an_executor_are_offered(mocker, tmp_path):
    """A deck file WindBot has no executor for makes it load a random deck."""
    from ui import room_ui

    mocker.patch("ui.room_ui._install_root", return_value=tmp_path)
    decks_dir = tmp_path / "Decks"
    decks_dir.mkdir()
    (decks_dir / "AI_BlueEyes.ydk").write_text("deck")
    (decks_dir / "AI_NotAThing.ydk").write_text("deck")

    assert room_ui._get_available_bot_decks() == ["Blue-Eyes"]


def test_every_bot_we_offer_resolves_to_a_windbot_key():
    """The whole shipped catalogue must round trip, keys and file names alike."""
    from bot import deck_catalogue, launcher

    assert len(deck_catalogue.KEY_TO_DECK_FILE) >= 50
    for key, deck_file in deck_catalogue.KEY_TO_DECK_FILE.items():
        assert launcher._deck_file_name_to_windbot_key(key) == key
        assert launcher._deck_file_name_to_windbot_key(deck_file) == key
        assert launcher._deck_file_name_to_windbot_key(f"{deck_file}.ydk") == key


def test_the_deck_catalogue_matches_the_executors_on_disk():
    """Regenerate with scripts/generate_bot_decks.py when this fails."""
    import sys

    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "scripts"))
    try:
        import generate_bot_decks as generator
    finally:
        sys.path.pop(0)

    catalogue = generator.playable(
        generator.parse_executors(root / "Game" / "AI" / "Decks"), root / "Decks"
    )
    rendered = generator.render(catalogue)
    current = (root / "src" / "bot" / "deck_catalogue.py").read_text(encoding="utf-8")
    assert current == rendered, "run python scripts/generate_bot_decks.py"


def test_every_bots_json_entry_is_playable():
    """An entry naming a deck we cannot pilot would offer a bot that never comes."""
    import json

    from bot import deck_catalogue

    root = Path(__file__).resolve().parent.parent
    entries = json.loads((root / "bots.json").read_text(encoding="utf-8"))
    unknown = sorted(e["deck"] for e in entries if e["deck"] not in deck_catalogue.KEY_TO_DECK_FILE)
    assert unknown == []
