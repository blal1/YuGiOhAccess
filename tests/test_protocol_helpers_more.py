import base64
import io
import socket
import struct
from unittest.mock import MagicMock

import pytest


def test_location_conversion_zone_keys_and_human_readable(mocker):
    from game.card import card_constants
    from game.card.location_conversion import LocationConversion

    client = MagicMock()
    client.what_player_am_i = 0
    mocker.patch("game.card.location_conversion._", side_effect=lambda s: s)

    assert LocationConversion.from_zone_key(client, "pm2").to_zone_key() == "pm2"
    assert LocationConversion.from_zone_key(client, "om2").controller == 1
    assert LocationConversion.from_zone_key(client, "q0").to_zone_key() == "q0"
    assert LocationConversion.from_zone_key(client, "oq0").to_zone_key() == "q1"
    assert LocationConversion.from_zone_key(client, "pf").location == card_constants.LOCATION.FIELD_ZONE
    assert LocationConversion.from_zone_key(client, "opf").controller == 1
    assert LocationConversion.from_zone_key(client, "od").controller == 1
    assert LocationConversion.from_zone_key(client, "pd").location == card_constants.LOCATION.DECK
    assert LocationConversion.from_zone_key(client, "bad") is None
    assert LocationConversion.from_zone_key(client, "pf0").to_zone_key() == "pf0"

    locations = [
        ("pd1", card_constants.LOCATION.DECK),
        ("ps1", card_constants.LOCATION.SPELL_AND_TRAP_ZONE),
        ("pg1", card_constants.LOCATION.GRAVE),
        ("pr1", card_constants.LOCATION.REMOVED),
        ("ph1", card_constants.LOCATION.HAND),
        ("px1", card_constants.LOCATION.EXTRA),
        ("pp1", card_constants.LOCATION.PENDULUM_ZONE),
    ]
    for key, enum_value in locations:
        converted = LocationConversion.from_zone_key(client, key)
        assert converted.location == enum_value
        assert converted.to_zone_key() == key
        assert "Your" in converted.to_human_readable()

    assert LocationConversion(client, 0, card_constants.LOCATION.MONSTER_ZONE, 6).to_zone_key() == "q1"
    assert LocationConversion(client, 1, card_constants.LOCATION.MONSTER_ZONE, 6).to_zone_key() == "q0"
    assert LocationConversion(client, 0, card_constants.LOCATION.FIELD_ZONE, 0).to_zone_key() == "pf0"
    assert "field zone" in LocationConversion(client, 0, card_constants.LOCATION.FIELD_ZONE, 0).to_human_readable()
    loc = LocationConversion(client, 1, card_constants.LOCATION.MONSTER_ZONE, 0)
    assert loc == "om0"
    assert "LocationConversion" in repr(loc)
    assert "unknown location" in LocationConversion(client, 0, 999, 0).to_human_readable()


def test_ydke_json_windbot_roundtrips_and_errors(mocker):
    from game.card.ydke import Deck, URLParseError

    main = struct.pack("<3i", 1, 2, 3)
    extra = struct.pack("<2i", 4, 5)
    side = struct.pack("<1i", 6)
    url = "ydke://{}!{}!{}".format(
        base64.standard_b64encode(main).decode("ascii"),
        base64.standard_b64encode(extra).decode("ascii"),
        base64.standard_b64encode(side).decode("ascii"),
    )
    deck = Deck.from_ydke(url)
    assert deck.cards == [1, 2, 3, 4, 5]
    assert deck.side == [6]
    assert Deck.from_ydke(deck.to_ydke()).cards == deck.cards

    with pytest.raises(URLParseError):
        Deck.from_ydke("not-a-ydke")
    with pytest.raises(URLParseError):
        Deck.from_ydke("ydke://abc!")
    with pytest.raises(URLParseError):
        Deck.from_ydke("ydke://AA==!")
    with pytest.raises(URLParseError):
        Deck.from_ydke("ydke://AAAA")
    with pytest.raises(URLParseError):
        Deck.from_json("{")

    parsed = Deck.from_json('{"main": {"0": 7}, "side": {"0": 8}}')
    assert parsed.cards == [7]
    assert parsed.side == [8]
    assert "Main+extra deck" in str(parsed)

    windbot = Deck.from_windbot_format("#created by test\n#main\n10\n#extra\n20\n!side\n30\n")
    assert windbot.cards == [10]
    assert windbot.side == [30]
    with pytest.raises(ValueError):
        Deck.from_windbot_format("#main\nnot-int")

    def fake_card(code):
        card = MagicMock()
        card.extra = code == 20
        return card

    mocker.patch("game.card.ydke.Card", side_effect=fake_card)
    exported = Deck([10, 20], [30]).to_windbot_format()
    assert "#main" in exported
    assert "#extra" in exported
    assert "!side" in exported
    assert "10" in exported and "20" in exported and "30" in exported


def test_game_socket_send_recv_connect_and_disconnect(mocker):
    from game.edo.game_socket import GameSocket

    sock = MagicMock()
    mocker.patch("socket.socket", return_value=sock)
    game_socket = GameSocket()

    game_socket.connect("host", 1234, timeout=3)
    sock.settimeout.assert_any_call(3)
    sock.connect.assert_called_with(("host", 1234))
    sock.settimeout.assert_any_call(None)

    game_socket.send(9, b"abc")
    sock.sendall.assert_called_with(struct.pack("hB", 4, 9) + b"abc")

    packet1 = struct.pack("hB", 2, 7) + b"x"
    packet2 = struct.pack("hB", 3, 8) + b"yz"
    sock.recv.side_effect = [packet1 + packet2]
    assert game_socket.recv() == (7, 1, b"x")
    assert game_socket.recv() == (8, 2, b"yz")
    sock.recv.side_effect = [b""]
    assert game_socket.recv() == (None, None, None)
    game_socket.disconnect()
    sock.close.assert_called_once()


def test_game_socket_connect_errors(mocker):
    from game.edo.game_socket import GameSocket

    sock = MagicMock()
    mocker.patch("socket.socket", return_value=sock)
    sock.connect.side_effect = socket.timeout
    with pytest.raises(Exception, match="Connection timed out"):
        GameSocket().connect("host", 1)

    sock.connect.side_effect = OSError("boom")
    with pytest.raises(Exception, match="Failed to connect"):
        GameSocket().connect("host", 1)


def test_discord_presence_queue_reconnect_and_stop(mocker):
    from core.discord_presence import DiscordPresenceManager
    import core.discord_presence as presence_module

    fake_presence = MagicMock()
    mocker.patch("core.discord_presence.Presence", return_value=fake_presence)
    manager = DiscordPresenceManager("client")

    assert manager.default_buttons[0]["label"]
    manager.update_presence(state="Ready")
    queued = manager.update_queue.get_nowait()
    assert queued["state"] == "Ready"
    assert "buttons" in queued

    manager.rpc = fake_presence
    manager.reconnect()
    assert manager.is_connected is True
    fake_presence.connect.assert_called()

    fake_presence.connect.side_effect = presence_module.pypresence.exceptions.DiscordNotFound
    manager.reconnect()
    assert manager.is_connected is False
    fake_presence.connect.side_effect = presence_module.pypresence.exceptions.PipeClosed
    manager.reconnect()
    assert manager.is_connected is False

    manager.stop()
    assert manager.running is False
    assert manager.update_queue.get_nowait() is None


def test_discord_presence_run_processes_update_and_cleanup(mocker):
    from core.discord_presence import DiscordPresenceManager

    fake_presence = MagicMock()
    fake_presence.update.side_effect = lambda **kwargs: setattr(manager, "running", False)
    mocker.patch("core.discord_presence.Presence", return_value=fake_presence)
    mocker.patch("core.discord_presence.time.sleep")
    manager = DiscordPresenceManager("client")
    manager.update_presence(state="Dueling")

    manager.run()

    fake_presence.connect.assert_called_once()
    fake_presence.update.assert_called_once()
    fake_presence.clear.assert_called_once()
    fake_presence.close.assert_called_once()


def test_discord_presence_run_handles_pipe_closed_and_sentinel(mocker):
    import core.discord_presence as presence_module
    from core.discord_presence import DiscordPresenceManager

    fake_presence = MagicMock()
    fake_presence.update.side_effect = presence_module.pypresence.exceptions.PipeClosed
    mocker.patch("core.discord_presence.Presence", return_value=fake_presence)
    mocker.patch("core.discord_presence.time.sleep", side_effect=lambda _: setattr(manager, "running", False))
    manager = DiscordPresenceManager("client")
    manager.update_presence(state="Dueling")

    manager.run()

    assert fake_presence.connect.call_count >= 2

    fake_presence.reset_mock()
    fake_presence.clear.side_effect = presence_module.pypresence.exceptions.PipeClosed
    manager = DiscordPresenceManager("client")
    manager.update_queue.put(None)
    manager.run()
    fake_presence.close.assert_not_called()


def test_discord_presence_cleanup_skips_clear_when_not_connected(mocker):
    import core.discord_presence as presence_module
    from core.discord_presence import DiscordPresenceManager

    fake_presence = MagicMock()
    fake_presence.connect.side_effect = presence_module.pypresence.exceptions.DiscordNotFound
    mocker.patch("core.discord_presence.Presence", return_value=fake_presence)
    manager = DiscordPresenceManager("client")
    manager.update_queue.put(None)

    manager.run()

    assert manager.is_connected is False
    fake_presence.clear.assert_not_called()
    fake_presence.close.assert_not_called()


def test_discord_presence_cleanup_catches_assertion_error(mocker):
    from core.discord_presence import DiscordPresenceManager

    fake_presence = MagicMock()
    fake_presence.clear.side_effect = AssertionError("not connected")
    mocker.patch("core.discord_presence.Presence", return_value=fake_presence)
    manager = DiscordPresenceManager("client")
    manager.update_queue.put(None)

    manager.run()

    fake_presence.clear.assert_called_once()
    fake_presence.close.assert_not_called()


def test_servers_list_and_local_availability(mocker):
    from game import servers

    mocker.patch("server.embedded.is_running", return_value=True)
    all_servers = servers.get_servers()

    assert [server.name for server in all_servers] == [
        "Local (Offline)",
        "Test Server",
        "EU Central (Casual)",
        "EU Central (Competitive)",
        "US West (Casual)",
        "US West (Competitive)",
    ]
    assert all_servers[0].is_available(None) is True

    status = MagicMock(version="v1", error=None, ocgcore_path="core", available=True)
    mocker.patch("server.embedded.is_running", side_effect=[False, True])
    start = mocker.patch("server.embedded.start_local_server")
    mocker.patch("server.embedded.engine_status", return_value=status)
    mocker.patch("game.servers.time.time", side_effect=[0, 0, 2])
    mocker.patch("game.servers.time.sleep")
    assert servers.LocalServer().is_available(None) is True
    start.assert_called_once()

    status = MagicMock(version=None, error=None, ocgcore_path=None, available=False)
    mocker.patch("server.embedded.is_running", return_value=True)
    mocker.patch("server.embedded.engine_status", return_value=status)
    assert servers.LocalServer().is_available(None) is True


def test_edo_struct_reprs_bytes_and_helpers():
    import ctypes

    from game.edo import structs

    limits = structs.DeckLimits()
    limits.main.min = 40
    limits.main.max = 60
    limits.extra.max = 15
    assert "Boundary min: 40 max: 60" in repr(limits.main)
    assert "DeckLimits main:" in repr(limits)

    deck = structs.Deck()
    deck.set_main_deck([1, 2])
    deck.set_side_deck([3])
    packed = bytes(deck)
    assert packed.startswith(struct.pack("ii", 2, 1))

    host = structs.HostInfo()
    host.starting_lp = 8000
    host.t0_count = 2
    assert "starting_lp: 8000" in repr(host)

    chat = structs.StocChat2()
    chat.type = structs.Chat2Type.DUELIST
    chat.is_team = 1
    for index, char in enumerate("Bilal"):
        chat.client_name[index] = ord(char)
    for index, char in enumerate("Hello"):
        chat.msg[index] = ord(char)
    assert "Bilal" in repr(chat)
    assert "Hello" in repr(chat)

    err = structs.ErrorMSG()
    err.msg = 2
    err.code = 123
    assert repr(err) == "<ErrorMSG msg: 2 code: 123>"

    count = structs._Count()
    count.got = 61
    count.min = 40
    count.max = 60
    assert "got: 61" in repr(count)

    deck_error = structs.DeckErrrorMSG()
    deck_error.msg = 1
    deck_error.type = 7
    deck_error.count = count
    deck_error.code = 42
    assert "DeckErrrorMSG" in repr(deck_error)

    created = structs.StocCreateGame()
    created.id = 99
    assert repr(created) == "<StocCreateGame id: 99>"

    joined = structs.StocJoinGame()
    joined.info.starting_lp = 4000
    assert "StocJoinGame" in repr(joined)

    entered = structs.StocPlayerEnter()
    for index, char in enumerate("Player"):
        entered.name[index] = ord(char)
    entered.pos = 3
    assert "Player" in repr(entered)

    change = structs.StocPlayerChange()
    change.status = (2 << 4) | structs.StocChangeType.READY
    assert change.is_ready() is True
    assert change.position() == 2
    assert "ready: True" in repr(change)
    for status_name in ("NOT_READY", "LEAVE", "SPECTATE"):
        change.status = (1 << 4) | getattr(structs.StocChangeType, status_name)
        assert status_name.lower().replace("_", "")[:5] in repr(change).replace("_", "").lower()

    type_change = structs.StocTypeChange()
    type_change.type = (1 << 4) | 5
    assert type_change.is_host() == 1
    assert type_change.position() == 5
    assert "is_host: 1" in repr(type_change)

    for left, right, expected_left, expected_right in [
        (structs.RPS.ROCK, structs.RPS.PAPER, "rock", "paper"),
        (structs.RPS.SCISSORS, structs.RPS.ROCK, "scissors", "rock"),
        (0, 0, "result0: ", "result1: "),
    ]:
        result = structs.StocRPSResult()
        result.result0 = left
        result.result1 = right
        rendered = repr(result)
        assert expected_left in rendered
        assert expected_right in rendered

    timer = structs.StocTimeLimit()
    timer.team = 1
    timer.time = 180
    assert repr(timer) == "<StocTimeLimit team: 1 time: 180 seconds>"
