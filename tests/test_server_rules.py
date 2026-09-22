"""Rules the bundled server never enforced, and records it never kept.

It accepted any deck at all, so a deck of three cards started a duel the core
could not run. It never offered a rematch, never sent a replay, and a
spectator who joined mid duel saw an empty screen.
"""

import asyncio
import struct

import pytest

from game.edo import structs
from game.edo.message_constants import MSG_DRAW, MSG_SELECT_IDLECMD, MSG_START, MSG_WIN
from server import deck_check, replay
from server.duel import DuelInstance
from server.lobby import LobbyServer, Room, _deck_limits
from server.protocol import RoomState, ServerPacket
from tests.test_duel_routing import FakeConn, FakeEngine


def _legal_deck():
    """Forty distinct cards: the smallest main deck the rules allow."""
    return list(range(1, 41))


def _room(lobby=None, **host_info):
    lobby = lobby or LobbyServer(duel_engine=FakeEngine())
    room = Room(1, host_info, lobby=lobby)
    lobby.rooms[room.room_id] = room
    return lobby, room


def _join(room, conn, slot):
    room.players[slot] = conn
    conn.slot = slot
    conn.room = room
    conn.deck_error = None
    conn.wants_rematch = False
    conn.ready = True
    return conn


def _packets(conn, packet_id):
    return [data for sent_id, data in conn.sent if sent_id == packet_id]


# ----------------------------------------------------------- deck checking --

def test_a_legal_deck_passes():
    assert deck_check.check_deck(_legal_deck(), [], []) is None


@pytest.mark.parametrize("main,expected", [
    ([1, 2, 3], deck_check.DECKERROR_MAINCOUNT),
    (list(range(1, 62)), deck_check.DECKERROR_MAINCOUNT),
])
def test_a_main_deck_of_the_wrong_size_is_refused(main, expected):
    error = deck_check.check_deck(main, [], [])
    assert error is not None and error.type == expected
    assert error.minimum == 40 and error.maximum == 60


def test_an_oversized_extra_or_side_deck_is_refused():
    too_much_extra = deck_check.check_deck(_legal_deck(), list(range(100, 116)), [])
    assert too_much_extra.type == deck_check.DECKERROR_EXTRACOUNT

    too_much_side = deck_check.check_deck(_legal_deck(), [], list(range(100, 116)))
    assert too_much_side.type == deck_check.DECKERROR_SIDECOUNT


def test_a_fourth_copy_of_a_card_is_refused():
    # The filler starts at 100 so it cannot quietly add a fifth copy of 7.
    deck = [7, 7, 7, 7] + list(range(100, 136))
    error = deck_check.check_deck(deck, [], [])
    assert error.type == deck_check.DECKERROR_CARDCOUNT
    assert (error.code, error.got, error.maximum) == (7, 4, 3)


def test_the_banlist_decides_the_limit_when_there_is_one():
    class OneCopyOnly:
        def get_limit(self, code):
            return 1 if code == 7 else 3

    deck = [7, 7] + list(range(100, 138))
    error = deck_check.check_deck(deck, [], [], banlist=OneCopyOnly())
    assert error.type == deck_check.DECKERROR_LFLIST
    assert (error.code, error.got, error.maximum) == (7, 2, 1)


def test_a_card_the_server_has_never_heard_of_is_refused():
    error = deck_check.check_deck(_legal_deck(), [], [], known_card=lambda code: code != 13)
    assert error.type == deck_check.DECKERROR_UNKNOWNCARD
    assert error.code == 13


def test_a_deck_error_is_the_shape_the_client_reads_back():
    import ctypes

    error = deck_check.DeckError(deck_check.DECKERROR_MAINCOUNT, got=39, minimum=40, maximum=60)
    raw = error.to_bytes()
    assert len(raw) == ctypes.sizeof(structs.DeckErrrorMSG)
    parsed = structs.DeckErrrorMSG.from_buffer_copy(raw)
    assert parsed.type == deck_check.DECKERROR_MAINCOUNT
    assert (parsed.count.got, parsed.count.min, parsed.count.max) == (39, 40, 60)


def test_zeroed_limits_mean_unspecified_rather_than_nothing_allowed():
    """A create packet that left the limits alone must not ban every deck."""
    empty = bytes(structs.DeckLimits())
    limits = _deck_limits(empty)
    assert (limits.main.min, limits.main.max) == (40, 60)


def test_the_server_refuses_a_bad_deck_when_it_arrives():
    lobby, room = _room()
    player = _join(room, FakeConn("Human", 0), 0)
    player.deck_side = []

    payload = struct.pack("<II", 3, 0) + struct.pack("<III", 1, 2, 3)
    asyncio.run(lobby._handle_update_deck(player, payload))

    assert player.deck_error is not None
    assert _packets(player, ServerPacket.ERROR_MSG)


def test_a_room_can_turn_deck_checking_off():
    lobby, room = _room(no_check_deck=1)
    player = _join(room, FakeConn("Human", 0), 0)
    player.deck_side = []

    payload = struct.pack("<II", 3, 0) + struct.pack("<III", 1, 2, 3)
    asyncio.run(lobby._handle_update_deck(player, payload))

    assert player.deck_error is None
    assert not _packets(player, ServerPacket.ERROR_MSG)


def test_a_duel_does_not_start_on_an_illegal_deck():
    lobby, room = _room(t0_count=1, t1_count=1)
    host = _join(room, FakeConn("Human", 0, main=[1, 2, 3], extra=[]), 0)
    guest = _join(room, FakeConn("Other", 1, main=_legal_deck(), extra=[]), 1)
    host.deck_side = guest.deck_side = []

    started = asyncio.run(lobby._try_start_room(room, report_waiting=True))

    assert started is False
    assert room.duel is None
    assert _packets(host, ServerPacket.ERROR_MSG)


# ---------------------------------------------------------------- rematch ---

def _finished_room():
    lobby, room = _room(no_check_deck=1)
    host = _join(room, FakeConn("Human", 0), 0)
    guest = _join(room, FakeConn("Other", 1), 1)
    host.deck_side = guest.deck_side = []
    room.state = RoomState.ENDED
    return lobby, room, host, guest


def test_a_finished_duel_offers_a_rematch():
    lobby, room = _room(no_check_deck=1)
    host = _join(room, FakeConn("Human", 0), 0)
    guest = _join(room, FakeConn("Other", 1), 1)
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    room.duel = duel

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    assert _packets(host, ServerPacket.REMATCH)
    assert _packets(guest, ServerPacket.REMATCH)


def test_one_player_waits_while_the_other_decides(mocker):
    lobby, room, host, guest = _finished_room()
    started = mocker.patch.object(lobby, "_try_start_room", new=mocker.AsyncMock())

    asyncio.run(lobby._handle_rematch(host, bytes([1])))

    assert _packets(host, ServerPacket.REMATCH_WAIT)
    started.assert_not_awaited()


def test_two_yeses_start_the_duel_again(mocker):
    lobby, room, host, guest = _finished_room()
    started = mocker.patch.object(lobby, "_try_start_room", new=mocker.AsyncMock())

    asyncio.run(lobby._handle_rematch(host, bytes([1])))
    asyncio.run(lobby._handle_rematch(guest, bytes([1])))

    started.assert_awaited_once()
    assert room.state == RoomState.WAITING
    assert room.match_wins == [0, 0]
    assert all(not player.ready for player in room.players)


def test_a_refusal_tells_the_other_player(mocker):
    lobby, room, host, guest = _finished_room()
    mocker.patch.object(lobby, "_try_start_room", new=mocker.AsyncMock())

    asyncio.run(lobby._handle_rematch(host, bytes([0])))

    assert _packets(guest, ServerPacket.REMATCH_WAIT)
    assert _packets(guest, ServerPacket.CHAT_2)
    assert room.state == RoomState.WAITING


# ------------------------------------------------------- replay and catchup --

def test_a_replay_round_trips():
    recorder = replay.DuelReplay()
    recorder.add(bytes([MSG_START, 0, 1, 2]))
    recorder.add(bytes([MSG_DRAW, 0]))

    raw = recorder.to_bytes()

    assert replay.is_ours(raw)
    assert replay.read(raw) == [bytes([MSG_START, 0, 1, 2]), bytes([MSG_DRAW, 0])]


def test_an_empty_duel_produces_no_replay():
    assert replay.DuelReplay().to_bytes() == b""


def test_a_yrp_is_not_mistaken_for_one_of_ours():
    assert replay.is_ours(b"yrpX\x00\x00\x00\x00") is False
    assert replay.read(b"yrpX\x00\x00\x00\x00") == []


def test_a_truncated_replay_returns_what_it_can(caplog):
    recorder = replay.DuelReplay()
    recorder.add(bytes([MSG_DRAW, 0]))
    raw = recorder.to_bytes()

    with caplog.at_level("WARNING", logger="server.replay"):
        assert replay.read(raw[:-1]) == []


def test_the_duel_is_sent_to_the_players_when_it_ends():
    lobby, room = _room(no_check_deck=1)
    host = _join(room, FakeConn("Human", 0), 0)
    _join(room, FakeConn("Other", 1), 1)
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    room.duel = duel
    duel._replay.add(bytes([MSG_DRAW, 0]))

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    sent = _packets(host, ServerPacket.NEW_REPLAY)
    assert sent and replay.read(sent[0]) == [bytes([MSG_DRAW, 0])]


def test_a_spectator_is_caught_up_on_the_duel_so_far():
    lobby, room = _room(no_check_deck=1)
    _join(room, FakeConn("Human", 0), 0)
    _join(room, FakeConn("Other", 1), 1)
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    duel.set_first_player_slot(0)
    room.duel = duel
    room.state = RoomState.DUELING
    duel._replay.add(bytes([MSG_START, 0]) + b"\x00" * 14)
    duel._replay.add(bytes([MSG_SELECT_IDLECMD, 0]))

    watcher = FakeConn("Watcher", -1)
    watcher.room = room
    room.observers.append(watcher)
    asyncio.run(lobby._catch_up_spectator(watcher, room))

    assert _packets(watcher, ServerPacket.DUEL_START)
    catchup = _packets(watcher, ServerPacket.CATCHUP)
    assert catchup[0] == bytes([1]) and catchup[-1] == bytes([0])

    messages = _packets(watcher, ServerPacket.GAME_MSG)
    # The start message tells a spectator it holds no seat, rather than
    # handing it the first player's identity.
    assert messages[0][1] == 0x10
    assert bytes([MSG_SELECT_IDLECMD, 0]) in messages


def test_joining_a_room_mid_duel_makes_you_a_spectator():
    lobby, room = _room(no_check_deck=1, password="")
    _join(room, FakeConn("Human", 0), 0)
    room.players[1] = None
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    room.duel = duel
    room.state = RoomState.DUELING

    latecomer = FakeConn("Watcher", -1)
    latecomer.name = "Watcher"
    join = structs.JoinGame()
    join.id = room.room_id
    asyncio.run(lobby._handle_join_game(latecomer, bytes(join)))

    # The empty seat is not offered while a duel is running.
    assert latecomer.slot == -1
    assert latecomer in room.observers
    assert _packets(latecomer, ServerPacket.CATCHUP)


# -------------------------------------------------------------- surrender ---

def test_a_spectator_cannot_surrender_somebody_elses_duel():
    lobby, room = _room(no_check_deck=1)
    host = _join(room, FakeConn("Human", 0), 0)
    _join(room, FakeConn("Other", 1), 1)
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    duel.set_first_player_slot(0)
    room.duel = duel

    watcher = FakeConn("Watcher", -1)
    watcher.room = room
    room.observers.append(watcher)

    asyncio.run(duel.handle_surrender(watcher))

    # Nothing was decided, and in particular nobody won.
    assert room.games_played == 0
    assert not any(data[:1] == bytes([MSG_WIN]) for data in _packets(host, ServerPacket.GAME_MSG))
