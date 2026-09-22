import asyncio
import struct
from types import SimpleNamespace


def test_engine_path_resolution_uses_local_assets(tmp_path, mocker):
    from server.engine_config import resolve_engine_paths

    mocker.patch("server.engine_config.platform.system", return_value="Windows")
    core_dir = tmp_path / "src" / "data" / "core"
    core_dir.mkdir(parents=True)
    ocgcore = core_dir / "ocgcore.dll"
    ocgcore.write_bytes(b"fake")
    db_dir = tmp_path / "src" / "data" / "databases"
    db_dir.mkdir(parents=True)
    db = db_dir / "cards.cdb"
    db.write_bytes(b"fake")
    script_dir = tmp_path / "src" / "data" / "scripts"
    script_dir.mkdir()

    paths = resolve_engine_paths(root=tmp_path)

    assert paths.ocgcore_path == str(ocgcore)
    assert paths.db_paths == [str(db)]
    assert paths.script_dir == str(script_dir)
    assert paths.has_engine is True
    assert paths.has_databases is True
    assert paths.has_scripts is True


def test_lobby_create_join_packets_match_client_structs():
    from game.edo import structs, structs_utils
    from server.lobby import LobbyServer, Room

    create = structs.CreateGame()
    create.host_info.banlist_hash = 123
    create.host_info.duel_rule = 5
    create.host_info.starting_lp = 8000
    create.host_info.starting_draw_count = 5
    create.host_info.draw_count_per_turn = 1
    create.host_info.time_limit_in_seconds = 180
    create.host_info.t0_count = 2
    create.host_info.t1_count = 2
    create.host_info.best_of = 3
    create.name = structs_utils.string_to_u16("Room", 20)
    create.password = structs_utils.string_to_u16("pw", 20)
    create.notes = b"notes"

    info = LobbyServer._parse_host_info(bytes(create))

    assert info["banlist_hash"] == 123
    assert info["start_lp"] == 8000
    assert info["t0_count"] == 2
    assert info["t1_count"] == 2
    assert info["best_of"] == 3
    assert info["name"] == "Room"
    assert info["password"] == "pw"
    assert info["notes"] == "notes"

    room = Room(42, info)
    import json
    from server.room_api import _json_dumps
    room_json_text = _json_dumps({"rooms": [room.to_json()]})
    room_payload = json.loads(room_json_text)["rooms"][0]
    assert room_payload["banlist_hash"] == 123
    assert room_payload["lflist"] == 123
    assert room_payload["host_info"]["version"] == [0, 0, 0, 0]

    assert LobbyServer._encode_room_created(room) == (42).to_bytes(4, "little")
    # The join reply has to be exactly what the client parses it back into,
    # deck size limits and all. Written by hand it was twelve bytes short.
    import ctypes

    from game.edo import structs as client_structs

    joined = LobbyServer._encode_join_game(info)
    assert len(joined) == ctypes.sizeof(client_structs.StocJoinGame)
    parsed = client_structs.StocJoinGame.from_buffer_copy(joined)
    assert parsed.info.banlist_hash == 123
    assert parsed.info.starting_lp == 8000
    assert parsed.info.handshake == 4043399681
    assert parsed.info.t0_count == 2
    assert parsed.info.best_of == 3
    assert (parsed.info.limits.main.min, parsed.info.limits.main.max) == (40, 60)


def test_lobby_join_uses_numeric_room_id_from_join_struct():
    from game.edo import structs, structs_utils
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket

    class FakeConn:
        def __init__(self):
            self.name = "Joiner"
            self.slot = -1
            self.room = None
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer()
    room = Room(99, {"password": "", "t0_count": 1, "t1_count": 1})
    lobby.rooms[99] = room
    conn = FakeConn()
    join = structs.JoinGame()
    join.id = 99
    join.password = structs_utils.string_to_u16("", 20)

    asyncio.run(lobby._handle_join_game(conn, bytes(join)))

    assert conn.room is room
    assert conn.slot == 0
    assert any(packet_id == ServerPacket.JOIN_GAME for packet_id, _ in conn.sent)


def test_lobby_join_accepts_windbot_join_packet_layout():
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket, encode_string_utf16

    class FakeConn:
        def __init__(self):
            self.name = "WindBot"
            self.slot = -1
            self.room = None
            self.ready = False
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer()
    room = Room(12345, {"password": "", "t0_count": 1, "t1_count": 1})
    lobby.rooms[12345] = room
    conn = FakeConn()
    # WindBot writes: int16 version, 2 padding bytes, int32 room id,
    # UTF-16 room info/password, int32 version.
    payload = (
        struct.pack("<H", 720937 & 0xFFFF)
        + b"\xAA\xBB"
        + struct.pack("<I", 0)
        + encode_string_utf16("12345", 20)
        + struct.pack("<I", 720937)
    )

    asyncio.run(lobby._handle_join_game(conn, payload))

    assert conn.room is room
    assert conn.slot == 0
    assert conn.ready is False
    assert any(packet_id == ServerPacket.JOIN_GAME for packet_id, _ in conn.sent)
    assert not any(packet_id == ServerPacket.ERROR_MSG for packet_id, _ in conn.sent)


def test_lobby_refuses_duel_start_without_ocgcore():
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket

    class FakeConn:
        def __init__(self, slot):
            self.name = f"P{slot}"
            self.slot = slot
            self.room = None
            self.ready = True
            self.deck_main = [1]
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer(duel_engine=None)
    room = Room(1, {"t0_count": 1, "t1_count": 1, "no_check_deck": 1})
    players = [FakeConn(0), FakeConn(1)]
    room.players = players
    for player in players:
        player.room = room
    conn = players[0]

    asyncio.run(lobby._handle_try_start(conn, b""))

    assert room.duel is None
    assert any(packet_id == ServerPacket.ERROR_MSG for packet_id, _ in conn.sent)
    assert any(packet_id == ServerPacket.CHAT_2 for player in players for packet_id, _ in player.sent)


def test_lobby_marks_windbot_ready_and_can_start_duel(mocker):
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket, RoomState
    from game.edo import structs, structs_utils

    class FakeConn:
        def __init__(self, name, slot=-1):
            self.name = name
            self.slot = slot
            self.room = None
            self.ready = False
            self.deck_main = [1]
            self.deck_side = []
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer(duel_engine=object())
    room = Room(77, {"password": "", "t0_count": 1, "t1_count": 1, "no_check_deck": 1})
    lobby.rooms[77] = room
    host = FakeConn("Host")
    room.add_player(host)
    host.ready = True

    bot = FakeConn("WindBot")
    join = structs.JoinGame()
    join.id = 77
    join.password = structs_utils.string_to_u16("", 20)

    asyncio.run(lobby._handle_join_game(bot, bytes(join)))

    assert bot.slot == 1
    assert bot.ready is True
    enter_packets = [data for packet_id, data in host.sent if packet_id == ServerPacket.PLAYER_ENTER]
    assert enter_packets[-1][-1] == 1
    assert any(packet_id == ServerPacket.PLAYER_CHANGE and data == b"\x19" for packet_id, data in host.sent)

    class FakeDuel:
        def __init__(self, room_arg, engine_arg):
            self.room = room_arg
            self.engine = engine_arg
            self.started = False

        async def start_rps(self):
            self.started = True

    mocker.patch("server.duel.DuelInstance", FakeDuel)
    asyncio.run(lobby._handle_try_start(host, b""))

    assert room.state == RoomState.RPS
    assert room.duel.started is True


def test_lobby_relays_chat_2_with_sender_name():
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket, encode_string_utf16

    class FakeConn:
        def __init__(self, name, slot):
            self.name = name
            self.slot = slot
            self.room = None
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer()
    room = Room(88, {"password": "", "no_check_deck": 1})
    sender = FakeConn("WindBot", 1)
    receiver = FakeConn("Player", 0)
    room.players = [receiver, sender]
    sender.room = room
    receiver.room = room

    asyncio.run(lobby._handle_chat(sender, encode_string_utf16("Ready", 256)))

    packets = [data for packet_id, data in receiver.sent if packet_id == ServerPacket.CHAT_2]
    assert len(packets) == 1
    assert len(packets[0]) == 554
    assert packets[0][0:2] == b"\x01\x00"
    assert packets[0][2:42].decode("utf-16-le").rstrip("\x00") == "WindBot"
    assert packets[0][42:554].decode("utf-16-le").rstrip("\x00") == "Ready"


def test_duel_start_sends_start_game_message_before_processing():
    from server.duel import DuelInstance, MSG_START
    from server.protocol import ServerPacket, RoomState

    class FakeConn:
        def __init__(self, name, slot, main, extra):
            self.name = name
            self.slot = slot
            self.deck_main = main
            self.deck_extra = extra
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    class FakeEngine:
        def create_duel(self, **kwargs):
            return 1

        def new_card(self, *args):
            pass

        def start_duel(self, handle):
            pass

    room = SimpleNamespace(
        host_info={"start_lp": 4000, "draw_count": 1, "start_hand": 5},
        players=[
            FakeConn("P0", 0, [1, 2, 3], [4]),
            FakeConn("P1", 1, [5, 6], []),
        ],
        observers=[],
        state=RoomState.WAITING,
    )
    duel = DuelInstance(room, FakeEngine())
    duel._turn_player = 0

    asyncio.run(duel._send_start_message())

    start0 = room.players[0].sent[0]
    start1 = room.players[1].sent[0]
    assert start0[0] == ServerPacket.GAME_MSG
    assert start0[1][0] == MSG_START
    assert struct.unpack_from("<IIHHHH", start0[1], 2) == (4000, 4000, 3, 1, 2, 0)
    assert struct.unpack_from("<IIHHHH", start1[1], 2) == (4000, 4000, 2, 0, 3, 1)


def test_ocgcore_preloads_global_scripts(tmp_path, mocker):
    from server.core import OcgCore

    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    (script_dir / "constant.lua").write_bytes(b"-- constants")
    (script_dir / "utility.lua").write_bytes(b"-- utility")

    engine = OcgCore.__new__(OcgCore)
    engine._script_dir = script_dir
    engine.load_script = mocker.Mock(return_value=True)

    duel = object()
    engine._preload_global_scripts(duel)

    assert [call.args[:2] for call in engine.load_script.call_args_list] == [
        (duel, "constant.lua"),
        (duel, "utility.lua"),
    ]


def test_ocgcore_script_reader_resolves_official_scripts(tmp_path, mocker):
    from server.core import OcgCore

    script_dir = tmp_path / "scripts"
    official_dir = script_dir / "official"
    official_dir.mkdir(parents=True)
    (official_dir / "c123.lua").write_bytes(b"-- card")

    engine = OcgCore.__new__(OcgCore)
    engine._script_dir = script_dir
    engine.load_script = mocker.Mock(return_value=True)

    result = engine._script_reader(None, object(), b"c123.lua")

    assert result == 1
    engine.load_script.assert_called_once()
    assert engine.load_script.call_args.args[1:] == ("c123.lua", b"-- card")


def test_lobby_try_start_auto_readies_local_bot_and_reports_missing_deck(mocker):
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket, RoomState

    class FakeConn:
        def __init__(self, name, slot):
            self.name = name
            self.slot = slot
            self.room = None
            self.ready = False
            self.deck_main = [1]
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    lobby = LobbyServer(duel_engine=object())
    room = Room(78, {"t0_count": 1, "t1_count": 1, "no_check_deck": 1})
    host = FakeConn("Host", 0)
    bot = FakeConn("", 1)
    room.players = [host, bot]
    for player in room.players:
        player.room = room
    host.ready = True
    bot.ready = False
    bot.deck_main = []

    asyncio.run(lobby._handle_try_start(host, b""))

    assert bot.ready is True
    assert room.state == RoomState.WAITING
    assert any(packet_id == ServerPacket.PLAYER_CHANGE and data == b"\x19" for packet_id, data in host.sent)
    assert any(packet_id == ServerPacket.CHAT_2 for packet_id, _ in host.sent)
    assert not any(packet_id == ServerPacket.ERROR_MSG for packet_id, _ in host.sent)

    class FakeDuel:
        def __init__(self, room_arg, engine_arg):
            self.started = False

        async def start_rps(self):
            self.started = True

    mocker.patch("server.duel.DuelInstance", FakeDuel)
    bot.deck_main = [2]
    asyncio.run(lobby._handle_try_start(host, b""))

    assert room.state == RoomState.RPS
    assert room.duel.started is True


def test_lobby_start_request_continues_when_bot_deck_arrives_late(mocker):
    from server.lobby import LobbyServer, Room
    from server.protocol import ServerPacket, RoomState
    from game.edo import structs

    class FakeConn:
        def __init__(self, name, slot):
            self.name = name
            self.slot = slot
            self.room = None
            self.ready = False
            self.deck_main = []
            self.deck_extra = []
            self.deck_side = []
            self.sent = []

        async def send(self, packet_id, data=b""):
            self.sent.append((packet_id, data))

    class FakeDuel:
        def __init__(self, room_arg, engine_arg):
            self.started = False

        async def start_rps(self):
            self.started = True

    mocker.patch("server.duel.DuelInstance", FakeDuel)
    lobby = LobbyServer(duel_engine=object())
    room = Room(79, {"t0_count": 1, "t1_count": 1, "no_check_deck": 1})
    host = FakeConn("Host", 0)
    bot = FakeConn("WindBot", 1)
    room.players = [host, bot]
    for player in room.players:
        player.room = room
    host.ready = True
    host.deck_main = [1]

    asyncio.run(lobby._handle_try_start(host, b""))

    assert room.start_requested is True
    assert room.state == RoomState.WAITING
    assert bot.ready is True
    assert any(packet_id == ServerPacket.CHAT_2 for packet_id, _ in host.sent)

    deck = structs.Deck()
    deck.set_main_deck([2])
    deck.set_side_deck([])
    asyncio.run(lobby._handle_update_deck(bot, bytes(deck)))

    assert bot.ready is True
    assert bot.deck_main == [2]
    assert room.state == RoomState.RPS
    assert room.duel.started is True


def test_local_server_availability_reflects_engine_status(mocker):
    from game.servers import LocalServer

    mocker.patch("server.embedded.is_running", return_value=True)
    mocker.patch(
        "server.embedded.engine_status",
        return_value=SimpleNamespace(
            available=False,
            version=None,
            error="ocgcore library not found",
            ocgcore_path="",
        ),
    )

    assert LocalServer().is_available(None) is False

    mocker.patch(
        "server.embedded.engine_status",
        return_value=SimpleNamespace(
            available=True,
            version=(40, 0),
            error="",
            ocgcore_path="ocgcore.dll",
        ),
    )

    assert LocalServer().is_available(None) is True


def test_ocgcore_loader_reports_windows_architecture_mismatch(tmp_path, mocker):
    from server.core import OcgCore

    dll = tmp_path / "ocgcore.dll"
    data = bytearray(256)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x014C)
    dll.write_bytes(data)

    mocker.patch("server.core.sys.platform", "win32")

    try:
        OcgCore._load_library(str(dll))
    except OSError as exc:
        assert "architecture mismatch" in str(exc)
    else:
        raise AssertionError("expected OSError")
