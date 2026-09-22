"""Two things the bundled server never did: run a match, and run a clock.

A best-of-three ended after game one, because nothing ever sent CHANGE_SIDE
and the client sat waiting for a side deck prompt that never came. And the
clock the client counts down was never told anything, so it counted from a
default it had invented.
"""

import asyncio
import struct

import pytest

from game.edo import structs
from game.edo.message_constants import MSG_SELECT_IDLECMD, MSG_WIN
from server.duel import DuelInstance
from server.lobby import LobbyServer, Room
from server.protocol import RoomState, ServerPacket
from tests.test_duel_routing import FakeConn, FakeEngine


def _match_room(best_of=3, time_limit=180, bot_name="WindBot"):
    lobby = LobbyServer(duel_engine=FakeEngine())
    room = Room(1, {"best_of": best_of, "time_limit": time_limit, "no_check_deck": 1}, lobby=lobby)
    room.players = [FakeConn("Human", 0), FakeConn(bot_name, 1)]
    for player in room.players:
        # The lobby reaches back from a connection to its room, the way a real
        # PlayerConnection does once it has joined one.
        player.room = room
    room.state = RoomState.DUELING
    lobby.rooms[room.room_id] = room
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    duel.set_first_player_slot(0)
    room.duel = duel
    return lobby, room, duel


def _packets(conn, packet_id):
    return [data for sent_id, data in conn.sent if sent_id == packet_id]


# ------------------------------------------------------------- the clock ---

def test_a_prompt_tells_the_player_how_long_they_have():
    """The client shows a countdown; it has to be told where the clock stands."""
    _lobby, room, duel = _match_room(time_limit=240)

    asyncio.run(duel._send_prompt(MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0])))

    clock = _packets(room.players[0], ServerPacket.TIME_LIMIT)
    assert clock, "the player being asked was never told their remaining time"
    parsed = structs.StocTimeLimit.from_buffer_copy(clock[0])
    assert parsed.team == 0
    assert parsed.time == 240


def test_the_clock_packet_is_the_size_the_client_reads():
    """Three bytes on the wire, packed, like every other packet here."""
    import ctypes

    assert ctypes.sizeof(structs.StocTimeLimit) == 3
    raw = struct.pack("<BH", 1, 65)
    parsed = structs.StocTimeLimit.from_buffer_copy(raw)
    assert (parsed.team, parsed.time) == (1, 65)


def test_thinking_time_comes_off_the_clock(mocker):
    _lobby, room, duel = _match_room(time_limit=100)

    async def scenario():
        await duel._send_prompt(MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0]))
        # Pretend the player took a while over it.
        duel._clock_started_at -= 30
        duel._stop_clock(0)

    asyncio.run(scenario())
    assert duel._time_left[0] == pytest.approx(70, abs=1)


def test_a_room_with_no_time_limit_does_not_send_a_clock():
    _lobby, room, duel = _match_room(time_limit=0)

    asyncio.run(duel._send_prompt(MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0])))

    assert not _packets(room.players[0], ServerPacket.TIME_LIMIT)


# ------------------------------------------------------------- the match ---

def test_winning_one_game_of_a_match_starts_side_decking():
    _lobby, room, duel = _match_room(best_of=3)

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    assert room.match_wins == [1, 0]
    assert room.games_played == 1
    assert room.state == RoomState.SIDE_DECKING
    # The human is asked to side; the bot, which cannot, is excused.
    assert _packets(room.players[0], ServerPacket.CHANGE_SIDE)
    assert room.awaiting_side_deck == {0}


def test_the_match_ends_when_someone_takes_it():
    _lobby, room, duel = _match_room(best_of=3)
    room.match_wins = [1, 0]
    room.games_played = 1

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    assert room.match_wins == [2, 0]
    assert room.match_is_decided()
    assert room.state == RoomState.ENDED
    assert not _packets(room.players[0], ServerPacket.CHANGE_SIDE)


def test_a_single_duel_never_asks_for_a_side_deck():
    _lobby, room, duel = _match_room(best_of=1)

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    assert room.state == RoomState.ENDED
    assert not _packets(room.players[0], ServerPacket.CHANGE_SIDE)


def test_submitting_a_side_deck_starts_the_next_game(mocker):
    lobby, room, _duel = _match_room(best_of=3)
    room.state = RoomState.SIDE_DECKING
    room.awaiting_side_deck = {0}
    started = mocker.patch.object(lobby, "_start_duel", new=mocker.AsyncMock())

    # main count, side count, then the cards
    payload = struct.pack("<II", 2, 1) + struct.pack("<III", 10, 11, 12)
    asyncio.run(lobby._handle_update_deck(room.players[0], payload))

    assert room.awaiting_side_deck == set()
    started.assert_awaited_once()


def test_a_player_who_sides_first_is_told_to_wait(mocker):
    lobby, room, _duel = _match_room(best_of=3, bot_name="Human Two")
    room.state = RoomState.SIDE_DECKING
    room.awaiting_side_deck = {0, 1}
    started = mocker.patch.object(lobby, "_start_duel", new=mocker.AsyncMock())

    payload = struct.pack("<II", 1, 0) + struct.pack("<I", 10)
    asyncio.run(lobby._handle_update_deck(room.players[0], payload))

    assert room.awaiting_side_deck == {1}
    assert _packets(room.players[0], ServerPacket.WAITING_SIDE)
    started.assert_not_awaited()


def test_two_humans_both_have_to_side_before_the_next_game():
    _lobby, room, duel = _match_room(best_of=3, bot_name="Human Two")

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 0])))

    assert room.awaiting_side_deck == {0, 1}
    assert _packets(room.players[0], ServerPacket.CHANGE_SIDE)
    assert _packets(room.players[1], ServerPacket.CHANGE_SIDE)


def test_a_surrender_counts_towards_the_match():
    _lobby, room, duel = _match_room(best_of=3)

    asyncio.run(duel.handle_surrender(room.players[0]))

    # Surrendering hands the game to the other seat.
    assert room.match_wins == [0, 1]
    assert room.games_played == 1
