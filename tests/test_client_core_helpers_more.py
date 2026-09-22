import io
import json
import struct
from unittest.mock import MagicMock

import pytest


def _client_without_init():
    from game.client import Client

    client = Client.__new__(Client)
    client.what_player_am_i = 0
    return client


def test_config_load_save_get_set(tmp_path):
    from core.config import Config

    defaults = {"volume": 0.5, "ip_cache": {}}
    cfg = Config(defaults)
    missing = tmp_path / "missing.json"
    cfg.load(missing)
    assert cfg.get("volume") == 0.5

    bad = tmp_path / "bad.json"
    bad.write_text("{")
    cfg.load(bad)
    assert cfg.data == defaults

    good = tmp_path / "good.json"
    good.write_text(json.dumps({"volume": 0.8}))
    cfg.load(good)
    assert cfg.get("volume") == 0.8
    assert cfg.get("ip_cache") == {}
    assert cfg.get("ui_language", "en") == "en"
    cfg.set("nickname", "Tester")
    assert json.loads(good.read_text())["nickname"] == "Tester"

    explicit = tmp_path / "explicit.json"
    cfg.save(explicit)
    assert explicit.exists()


def test_i18n_available_setup_and_plural_context(mocker, tmp_path, write_catalogue):
    import core.i18n as i18n

    mocker.patch.object(i18n, "_locale_dir", tmp_path)
    assert i18n.get_locale_dir() == tmp_path
    assert i18n.get_available_languages() == {"en": "English"}

    write_catalogue(tmp_path / "fr" / "LC_MESSAGES" / "yugiohaccess.mo")
    write_catalogue(tmp_path / "unknown" / "LC_MESSAGES" / "yugiohaccess.mo")
    langs = i18n.get_available_languages()
    assert langs["fr"] == "Français"
    assert langs["unknown"] == "unknown"

    # A catalogue with nothing in it is not a language the player can pick:
    # choosing it would announce a change and then change nothing.
    write_catalogue(tmp_path / "de" / "LC_MESSAGES" / "yugiohaccess.mo", translations={})
    # Neither is a file that is not a catalogue at all.
    corrupt = tmp_path / "it" / "LC_MESSAGES" / "yugiohaccess.mo"
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"fake")
    offered = i18n.get_available_languages()
    assert "de" not in offered
    assert "it" not in offered

    fake_translation = MagicMock()
    fake_translation.gettext.side_effect = lambda s: f"t:{s}"
    fake_translation.ngettext.side_effect = lambda s, p, n: s if n == 1 else p
    fake_translation.pgettext.side_effect = lambda c, s: f"{c}:{s}"
    mocker.patch("core.i18n.gettext.translation", return_value=fake_translation)
    i18n.setup("fr")
    assert i18n._("Hello") == "t:Hello"
    assert i18n.ngettext("card", "cards", 2) == "cards"
    assert i18n.pgettext("zone", "field") == "zone:field"

    i18n.setup("en")
    assert i18n._("Hello") == "Hello"
    mocker.patch("core.i18n.gettext.translation", side_effect=FileNotFoundError)
    i18n.setup("de")
    assert i18n._("Hello") == "Hello"


def test_client_packet_wait_send_readers_and_specs(mocker):
    from game.card import card_constants
    from game.edo import structs

    client = _client_without_init()
    client.game_socket = MagicMock()
    client.packet_event = MagicMock()
    client.response_packet = (1, 2, b"ok")
    def mark_packet_received(timeout=None):
        client.response_packet = (1, 2, b"ok")
        return True
    client.packet_event.wait.side_effect = mark_packet_received
    assert client.wait_for_packet(1) == (1, 2, b"ok")
    client.packet_event.clear.assert_called_once()

    client.packet_event.wait.side_effect = None
    client.packet_event.wait.return_value = False
    with pytest.raises(TimeoutError):
        client.wait_for_packet(1, timeout=0)

    client.send(structs.ClientIdType.RESPONSE)
    client.game_socket.send.assert_called_with(structs.ClientIdType.RESPONSE)
    client.send(structs.ClientIdType.RESPONSE, bytearray(b"abc"))
    client.game_socket.send.assert_called_with(structs.ClientIdType.RESPONSE, b"abc")

    # The wire format is unsigned little endian; 0xff is LOCATION-sized data,
    # not -1, and reading it signed used to corrupt LOCATION.OVERLAY (0x80).
    buf = io.BytesIO(struct.pack("<B", 0xFF) + struct.pack("<H", 0xFFFE) + struct.pack("<I", 3) + struct.pack("<Q", 4))
    assert client.read_u8(buf) == 0xFF
    assert client.read_u16(buf) == 0xFFFE
    assert client.read_u32(buf) == 3
    assert client.read_u64(buf) == 4

    loc_buf = io.BytesIO(
        struct.pack("B", 1)
        + struct.pack("B", card_constants.LOCATION.HAND)
        + struct.pack("I", 2)
        + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    )
    assert client.read_location(loc_buf) == (
        1,
        card_constants.LOCATION.HAND,
        2,
        card_constants.POSITION.FACE_UP_ATTACK,
    )

    overlay_buf = io.BytesIO(
        struct.pack("B", 1)
        + struct.pack("B", card_constants.LOCATION.OVERLAY)
        + struct.pack("I", 3)
    )
    assert client.read_location(overlay_buf) == (1, card_constants.LOCATION.OVERLAY, 3, 0)

    specs = client.flag_to_usable_cardspecs(0x00000000)
    assert "pm0" in specs and "q0" in specs and "pf" in specs
    reversed_specs = client.flag_to_usable_cardspecs(0x01010101, reverse=True)
    assert "pm0" in reversed_specs and "ps0" in reversed_specs
    assert client.zone_label_to_useful_spec("pm0") == "pm1"
    assert client.zone_label_to_useful_spec("bad") is None
    assert client.useful_spec_to_location("q1") == (card_constants.LOCATION.MONSTER_ZONE, 6, False)
    assert client.useful_spec_to_location("om2") == (card_constants.LOCATION.MONSTER_ZONE, 2, True)
    assert client.useful_spec_to_location("ps0") == (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 0, False)
    assert client.useful_spec_to_location("pf0") == (card_constants.LOCATION.FIELD_ZONE, 0, False)
    assert client.useful_spec_to_location("pg0") == (card_constants.LOCATION.GRAVE, 0, False)
    assert client.useful_spec_to_location("pd0") == (card_constants.LOCATION.DECK, 0, False)
    assert client.useful_spec_to_location("ph0") == (card_constants.LOCATION.HAND, 0, False)
    assert client.useful_spec_to_location("px0") == (card_constants.LOCATION.EXTRA, 0, False)
    assert client.useful_spec_to_location("pr0") == (card_constants.LOCATION.REMOVED, 0, False)
    packed = (card_constants.POSITION.FACE_UP_ATTACK << 24) | (4 << 16) | (card_constants.LOCATION.GRAVE << 8) | 1
    assert client.unpack_location(packed) == (
        1,
        card_constants.LOCATION.GRAVE,
        4,
        card_constants.POSITION.FACE_UP_ATTACK,
    )


def test_client_room_helpers(mocker):
    client = _client_without_init()
    client.room_id = 7
    client.server = MagicMock()
    client.server.get_room.side_effect = [None, "room"]
    mocker.patch("game.client.time.sleep")
    assert client.room == "room"
    client.room = "cached"
    client.room_id = None
    assert client.room == "cached"

    client = _client_without_init()
    client.room_id = 9
    client.server = MagicMock()
    client.server.get_room.return_value = None
    with pytest.raises(TimeoutError):
        client.room

    client = _client_without_init()
    client.duel_field = MagicMock()
    assert client.get_duel_field() is client.duel_field
    new_field = MagicMock()
    client.set_duel_field(new_field)
    assert client.duel_field is new_field


def test_client_get_card_and_cardlist(mocker):
    from game.card import card_constants

    from game.card.card import Card

    client = _client_without_init()
    # Only a real Card counts: an empty zone stores its own label here.
    found_card = Card(0)
    field = MagicMock()
    field.zones = {"ph1": MagicMock(card=found_card)}
    client.get_duel_field = MagicMock(return_value=field)
    assert client.get_card(0, card_constants.LOCATION.HAND, 1) is found_card

    field.zones = {}
    mocker.patch("game.client.time.sleep")
    assert client.get_card(0, card_constants.LOCATION.HAND, 1, max_retries=1) is None

    client.get_card = MagicMock(side_effect=[MagicMock(), MagicMock()])
    data = io.BytesIO()
    data.write(struct.pack("I", 2))
    data.write(struct.pack("I", 100) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", 1))
    data.write(struct.pack("I", 200) + struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.GRAVE) + struct.pack("I", 0))
    data.seek(0)
    cards = client.read_cardlist(data)
    assert len(cards) == 2

    client.get_card = MagicMock(side_effect=[MagicMock(), MagicMock()])
    data = io.BytesIO()
    data.write(struct.pack("I", 2))
    data.write(struct.pack("I", 100) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("B", 1) + struct.pack("B", 7))
    data.write(struct.pack("I", 200) + struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.GRAVE) + struct.pack("B", 0) + struct.pack("Q", 99) + struct.pack("B", 3))
    data.seek(0)
    cards = client.read_cardlist(data, extra=True, extra8=True, sequence_size=8)
    assert cards[0].data == 7

    data = io.BytesIO()
    data.write(struct.pack("I", 1))
    data.write(struct.pack("I", 300) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", 1) + struct.pack("Q", 88) + struct.pack("B", 2))
    data.seek(0)
    client.get_card = MagicMock(return_value=MagicMock())
    assert client.read_cardlist(data, extra=True)[0].data == 88

    fallback = MagicMock()
    fallback.set_location_and_position_info = MagicMock()
    card_cls = mocker.patch("game.client.Card", return_value=fallback)
    data = io.BytesIO()
    data.write(struct.pack("I", 1))
    data.write(struct.pack("I", 400) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", 4) + struct.pack("Q", 99) + struct.pack("B", 2))
    data.seek(0)
    client.get_card = MagicMock(return_value=None)
    cards = client.read_cardlist(data, extra=True)
    assert cards == [fallback]
    assert fallback.data == 99
    card_cls.assert_called_with(400)


def test_client_connection_listener_and_packet_handling(mocker):
    import game.client as client_module
    from game.client import Client
    from game.edo import structs

    server = MagicMock()
    server.address = "host"
    server.lobby_port = 123
    client = _client_without_init()
    client.server = server
    game_socket_cls = mocker.patch("game.client.GameSocket")
    client._connect()
    game_socket_cls.return_value.connect.assert_called_with("host", 123)
    client.disconnect()
    game_socket_cls.return_value.disconnect.assert_called_once()

    mocker.patch("game.client.utils.output")
    stack = MagicMock()
    mocker.patch("game.client.utils.get_ui_stack", return_value=stack)
    main_menu = MagicMock()
    mocker.patch("game.client.utils.get_main_menu_function", return_value=main_menu)
    client._handle_disconnect()
    stack.clear_ui_stack.assert_called_once()
    main_menu.assert_called_once()

    mocker.patch("game.client.wx.CallAfter", side_effect=lambda fn, *args: fn(*args))
    mocker.patch.dict("game.client.utils.packet_handlers", {}, clear=True)
    client.handle_packet(0xFE, 0, b"")
    client.handle_packet(structs.ServerIdType.PLAYER_ENTER, 1, b"x")
    assert game_socket_cls.called

    handler = MagicMock()
    mocker.patch.dict("game.client.utils.packet_handlers", {structs.ServerIdType.PLAYER_ENTER: handler}, clear=True)
    client.handle_packet(structs.ServerIdType.PLAYER_ENTER, 1, b"x")
    handler.assert_called_with(client, b"x", 1)

    listener = _client_without_init()
    listener.game_socket = MagicMock()
    listener.game_socket.recv.side_effect = OSError("lost")
    client_module.ORIGINAL_PACKET_LISTENER(listener)

    listener = _client_without_init()
    listener.game_socket = MagicMock()
    listener.game_socket.recv.return_value = (None, None, None)
    client_module.ORIGINAL_PACKET_LISTENER(listener)

    listener = _client_without_init()
    listener.game_socket = MagicMock()
    listener.expected_packet_id = structs.ServerIdType.PLAYER_ENTER
    listener.packet_event = MagicMock()
    listener.game_socket.recv.return_value = (structs.ServerIdType.PLAYER_ENTER, 1, b"x")
    handle_packet = mocker.patch.object(Client, "handle_packet", side_effect=SystemExit)
    with pytest.raises(SystemExit):
        client_module.ORIGINAL_PACKET_LISTENER(listener)
    assert listener.response_packet == (structs.ServerIdType.PLAYER_ENTER, 1, b"x")
    listener.packet_event.set.assert_called_once()
    handle_packet.assert_called_once_with(structs.ServerIdType.PLAYER_ENTER, 1, b"x")

    class DelayedSocketListener:
        expected_packet_id = structs.ServerIdType.PLAYER_ENTER

        def __init__(self):
            self.calls = 0
            self.socket = MagicMock()
            self.socket.recv.return_value = (structs.ServerIdType.PLAYER_ENTER, 1, b"x")
            self.packet_event = MagicMock()
            self.response_packet = None

        @property
        def game_socket(self):
            self.calls += 1
            return None if self.calls == 1 else self.socket

        def handle_packet(self, packet_id, packet_length, packet_data):
            raise SystemExit

    delayed = DelayedSocketListener()
    with pytest.raises(SystemExit):
        client_module.ORIGINAL_PACKET_LISTENER(delayed)
    assert delayed.response_packet == (structs.ServerIdType.PLAYER_ENTER, 1, b"x")


def test_client_join_and_create_room_paths(mocker):
    from game.client import Client
    from game.edo import structs

    server = MagicMock()
    mocker.patch("game.client.variables.config.get", return_value="Tester")
    mocker.patch("game.client.wx.CallAfter", side_effect=lambda fn, *args: fn(*args))
    error_handler = MagicMock()
    mocker.patch.dict("game.client.utils.packet_handlers", {structs.ServerIdType.ERROR_MSG: error_handler}, clear=True)

    fake_client = _client_without_init()
    fake_client.memory = MagicMock()
    fake_client._connect = MagicMock()
    fake_client.send = MagicMock()
    fake_client.wait_for_packet = MagicMock(return_value=(structs.ServerIdType.ERROR_MSG, 1, b"x"))
    mocker.patch("game.client.Client", side_effect=lambda server_arg: fake_client)
    assert Client.join_room(server, 7, "bad") is None
    error_handler.assert_called_with(None, b"x", 1)

    fake_client.wait_for_packet.return_value = (structs.ServerIdType.JOIN_GAME, len(bytes(structs.StocJoinGame())), bytes(structs.StocJoinGame()))
    joined = Client.join_room(server, 7, None, as_observer=True)
    assert joined.room_id == 7
    assert joined.memory.is_observer is True
    assert any(call.args[0] == structs.ClientIdType.TO_OBSERVER for call in fake_client.send.call_args_list)

    banlist = MagicMock()
    banlist.hash = 123
    manager_cls = mocker.patch("game.client.banlists.BanlistManager")
    manager_cls.return_value.get_banlist_by_name.return_value = banlist
    fake_client.memory = MagicMock()
    fake_client.send.reset_mock()
    created_packet = structs.StocCreateGame()
    created_packet.id = 55
    fake_client.wait_for_packet = MagicMock(return_value=(structs.ServerIdType.CREATE_GAME, len(bytes(created_packet)), bytes(created_packet)))
    mocker.patch("game.client.Client", side_effect=lambda server_arg: fake_client)
    mocker.patch("game.client.variables.DEV_OPTIONS", MagicMock(no_shuffle=True, draw=2))
    created = Client.create_room(server, {"name": "Room", "password": "", "notes": "", "best_of": 3, "team_count": 2})
    assert created.room_id == 55
    assert created.memory.room_banlist is banlist

    fake_client.wait_for_packet.return_value = (structs.ServerIdType.ERROR_MSG, 1, b"x")
    fallback = MagicMock()
    fallback.hash = 0
    manager_cls.return_value.get_banlist_by_name.side_effect = [None, fallback]
    assert Client.create_room(server, {"name": "Room", "password": "", "notes": "", "banlist": "unknown"}) is None

    fake_client.wait_for_packet.return_value = (structs.ServerIdType.ERROR_MSG, 1, b"x")
    manager_cls.return_value.get_banlist_by_name.side_effect = [None, None]
    assert Client.create_room(server, {"name": "Room", "password": "", "notes": "", "banlist": "missing"}) is None


def test_serverinfo_rooms_availability_and_dns(mocker):
    from game.serverinfo import EdoServerInformation

    cfg = MagicMock()
    cfg.get.return_value = {}
    mocker.patch("game.serverinfo.variables.config", cfg)
    server = EdoServerInformation("Name", "example.com", 80, 7911)
    mocker.patch("game.serverinfo.socket.gethostbyname", return_value="1.2.3.4")
    assert server.resolve_hostname_to_ip() == "1.2.3.4"
    cfg.set.assert_called()
    assert EdoServerInformation("IP", "127.0.0.1", 80, 1).resolve_hostname_to_ip() == "127.0.0.1"
    mocker.patch("game.serverinfo.socket.gethostbyname", side_effect=OSError("dns"))
    assert server.resolve_hostname_to_ip(required_refresh=True) == "example.com"

    server._get_room_json = MagicMock(return_value=[
        {"roomid": 2, "name": "b", "users": []},
        {"roomid": 1, "name": "a", "users": [{"name": "p"}]},
    ])
    assert server.get_room(1).roomid == 1
    assert server.get_room(99) is None
    server._get_room_json = MagicMock(return_value=None)
    assert server.get_room(1) is None
    assert server.list_rooms() == []
    server._get_room_json = MagicMock(return_value=[
        {"roomid": 2, "name": "b", "users": []},
        {"roomid": 1, "name": "a", "users": [{"name": "p"}]},
    ])
    rooms = server.list_rooms()
    assert [room.roomid for room in rooms] == [2, 1]
    assert "Name" in str(server)

    server.resolve_hostname_to_ip = MagicMock(return_value="1.2.3.4")
    server.room_session = MagicMock()
    server.room_session.head.return_value = MagicMock()
    mocker.patch("game.serverinfo.socket.create_connection")
    assert server.is_available(None) is True

    mocker.patch("game.serverinfo.socket.create_connection", side_effect=ConnectionRefusedError)
    assert server.is_available(None) is False
    mocker.patch("game.serverinfo.socket.create_connection", side_effect=RuntimeError("boom"))
    assert server.is_available(None) is False

    real_fetch_server = EdoServerInformation("Fetch", "example.com", 80, 7911)
    real_fetch_server.room_session = MagicMock()
    real_fetch_server.room_session.get.side_effect = [RuntimeError("stale ip"), MagicMock(json=MagicMock(return_value={"rooms": [{"roomid": 1, "users": []}]}))]
    real_fetch_server.resolve_hostname_to_ip = MagicMock(return_value="1.2.3.4")
    assert real_fetch_server._get_room_json() == [{"roomid": 1, "users": []}]
    assert real_fetch_server.resolve_hostname_to_ip.call_args_list[-1].args == (True,)

    real_fetch_server.room_session.get.side_effect = RuntimeError("offline")
    assert real_fetch_server._get_room_json(force_ip_refresh=True) is None
    real_fetch_server._get_room_json = MagicMock(return_value=[{"roomid": 1, "users": []}])
    real_fetch_server.join_room(1)
    server.room_session.head.side_effect = Exception("boom")
    assert server.is_available(None) is False
