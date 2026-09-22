"""Routing rules for the bundled server's duel loop.

A duel prompt belongs to exactly one player. Sending it to both made the bot
answer the human's prompts (and the other way round), which is why the client
saw actions it never took and card menus listing the opponent's hand.
"""

import asyncio
import struct
from types import SimpleNamespace

import pytest

from game.edo.message_constants import (
    MSG_ANNOUNCE_CARD,
    MSG_DRAW,
    MSG_NEW_TURN,
    MSG_SELECT_CARD,
    MSG_SELECT_IDLECMD,
    MSG_WAITING,
)
from server.duel import DuelInstance
from server.protocol import ServerPacket, RoomState


class FakeConn:
    def __init__(self, name, slot, main=None, extra=None):
        self.name = name
        self.slot = slot
        self.deck_main = main if main is not None else [1, 2, 3]
        self.deck_extra = extra if extra is not None else [4]
        self.sent = []

    async def send(self, packet_id, data=b""):
        self.sent.append((packet_id, data))

    def game_messages(self):
        return [data for packet_id, data in self.sent if packet_id == ServerPacket.GAME_MSG]


class FakeEngine:
    def __init__(self):
        self.responses = []

    def create_duel(self, **kwargs):
        return 1

    def new_card(self, *args):
        self.cards = getattr(self, "cards", [])
        self.cards.append(args)

    def start_duel(self, handle):
        pass

    def set_response(self, handle, payload):
        self.responses.append(payload)

    def destroy_duel(self, handle):
        self.destroyed = True

    def process(self, handle):
        return 1  # OCG_DUEL_STATUS_AWAITING

    def get_message(self, handle):
        return b""


def _duel(first_player_slot=0):
    # The real Room, not a stand-in: it is a plain object with no I/O, and a
    # hand written copy of its fields goes stale every time one is added.
    from server.lobby import Room

    room = Room(1, {"start_lp": 8000, "draw_count": 1, "start_hand": 5})
    room.players = [FakeConn("Human", 0), FakeConn("WindBot", 1)]
    room.state = RoomState.DUELING

    async def broadcast(packet_id, data=b"", exclude=None):
        for conn in room.players + room.observers:
            if conn and conn is not exclude:
                await conn.send(packet_id, data)

    async def broadcast_players(packet_id, data=b""):
        for conn in room.players:
            if conn:
                await conn.send(packet_id, data)

    async def broadcast_players_impl(packet_id, data=b""):
        for conn in room.players:
            if conn:
                await conn.send(packet_id, data)

    room.broadcast = broadcast
    room.broadcast_players = broadcast_players_impl

    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    duel.set_first_player_slot(first_player_slot)
    return duel, room


@pytest.mark.parametrize("first_slot", [0, 1])
@pytest.mark.parametrize("prompt", [MSG_SELECT_IDLECMD, MSG_SELECT_CARD, MSG_ANNOUNCE_CARD])
def test_prompt_reaches_only_the_player_it_addresses(first_slot, prompt):
    duel, room = _duel(first_player_slot=first_slot)
    msg = bytes([prompt, 0]) + b"\x01\x02\x03"

    asyncio.run(duel._send_game_message(prompt, msg))

    target_slot = first_slot  # core player 0 is whoever goes first
    other_slot = 1 - first_slot
    assert room.players[target_slot].game_messages() == [msg]
    assert room.players[other_slot].game_messages() == [bytes([MSG_WAITING])]


def test_informational_messages_still_reach_both_players():
    duel, room = _duel()
    msg = bytes([MSG_DRAW, 0]) + struct.pack("<I", 1)

    asyncio.run(duel._send_game_message(MSG_DRAW, msg))

    assert room.players[0].game_messages() == [msg]
    assert room.players[1].game_messages() == [msg]


def test_new_turn_does_not_corrupt_the_slot_mapping():
    duel, room = _duel(first_player_slot=1)

    # Core player 1 (room slot 0) takes the second turn.
    asyncio.run(duel._send_game_message(MSG_NEW_TURN, bytes([MSG_NEW_TURN, 1])))
    prompt = bytes([MSG_SELECT_IDLECMD, 1]) + b"\x00"
    asyncio.run(duel._send_game_message(MSG_SELECT_IDLECMD, prompt))

    assert prompt in room.players[0].game_messages()
    assert room.players[1].game_messages()[-1] == bytes([MSG_WAITING])


def test_start_message_tells_each_player_which_side_it_is():
    duel, room = _duel(first_player_slot=1)

    asyncio.run(duel._send_start_message())

    # Slot 1 goes first, so it is core player 0.
    assert room.players[1].game_messages()[0][1] == 0
    assert room.players[0].game_messages()[0][1] == 1


def test_response_from_the_wrong_player_is_ignored():
    duel, room = _duel()
    asyncio.run(duel._send_game_message(MSG_SELECT_CARD, bytes([MSG_SELECT_CARD, 0]) + b"\x00"))

    asyncio.run(duel.handle_response(room.players[1], b"\x01\x00\x00\x00"))
    assert duel.engine.responses == []

    asyncio.run(duel.handle_response(room.players[0], b"\x01\x00\x00\x00"))
    assert duel.engine.responses == [b"\x01\x00\x00\x00"]


def test_decks_load_on_the_side_the_player_actually_plays():
    duel, room = _duel(first_player_slot=1)
    room.players[0].deck_main = [11, 12]
    room.players[0].deck_extra = []
    room.players[1].deck_main = [21]
    room.players[1].deck_extra = []

    duel._load_deck(duel.slot_to_core_player(0), room.players[0])
    duel._load_deck(duel.slot_to_core_player(1), room.players[1])

    # new_card(handle, card_id, owner, controller, location, sequence, position)
    controller_of = {args[1]: args[3] for args in duel.engine.cards}
    assert controller_of[11] == 1  # slot 0 goes second -> core player 1
    assert controller_of[21] == 0  # slot 1 goes first -> core player 0


# ------------------------------------------------------------ client side ----

def _fake_client(player=-1):
    return SimpleNamespace(what_player_am_i=player, has_announced_turn_order=False)


def test_client_learns_its_side_from_the_start_message(mocker):
    from ui.duel_messages import start

    mocker.patch("ui.duel_messages.start.utils.output")
    client = _fake_client()

    start.set_player_index_from_play_type(client, 1)

    assert client.what_player_am_i == 1
    assert client.has_announced_turn_order is True


def test_client_ignores_the_start_message_play_type_when_spectating(mocker):
    from ui.duel_messages import start

    mocker.patch("ui.duel_messages.start.utils.output")
    client = _fake_client()

    start.set_player_index_from_play_type(client, 0x10)

    assert client.what_player_am_i == -1
    assert client.has_announced_turn_order is False


def test_client_logs_a_warning_for_a_prompt_meant_for_the_opponent(caplog):
    import ui

    client = _fake_client(player=0)
    packet = bytes([MSG_SELECT_CARD, 1]) + b"\x00"

    with caplog.at_level("WARNING", logger="ui"):
        ui.log_incoming_duel_message(client, packet)

    assert "SELECT_CARD" in caplog.text
    assert "player 1" in caplog.text


def test_retry_goes_back_to_the_player_whose_answer_was_rejected():
    from game.edo.message_constants import MSG_RETRY

    duel, room = _duel(first_player_slot=1)
    # Core player 0 is room slot 1; prompt it, then let it answer.
    asyncio.run(duel._send_game_message(MSG_SELECT_CARD, bytes([MSG_SELECT_CARD, 0]) + b"\x00"))
    asyncio.run(duel.handle_response(room.players[1], b"\xff\xff\xff\xff"))

    asyncio.run(duel._send_game_message(MSG_RETRY, bytes([MSG_RETRY])))

    assert room.players[1].game_messages()[-1] == bytes([MSG_RETRY])
    assert bytes([MSG_RETRY]) not in room.players[0].game_messages()


def test_surrender_names_the_other_player_as_winner():
    from game.edo.message_constants import MSG_WIN

    # Slot 1 goes first, so slot 0 (the human) is core player 1.
    duel, room = _duel(first_player_slot=1)

    asyncio.run(duel.handle_surrender(room.players[0]))

    win = [m for m in room.players[0].game_messages() if m[0] == MSG_WIN][0]
    assert win[1] == 0  # core player 0, which is slot 1
    assert win[2] == 0  # reason: surrender


def test_surrender_from_the_other_seat_too():
    from game.edo.message_constants import MSG_WIN

    duel, room = _duel(first_player_slot=1)

    asyncio.run(duel.handle_surrender(room.players[1]))

    win = [m for m in room.players[0].game_messages() if m[0] == MSG_WIN][0]
    assert win[1] == 1  # core player 1, which is slot 0


def test_extra_deck_monsters_do_not_stay_in_the_main_deck():
    from server.lobby import LobbyServer, PlayerConnection, Room

    class Engine:
        # 0x40 is fusion, 0x2000 synchro, 0x800000 xyz, 0x4000000 link.
        types = {1: 0x21, 2: 0x40, 3: 0x2000, 4: 0x800000, 5: 0x4000000, 6: 0x2}

        def card_type(self, code):
            return self.types.get(code, 0)

    server = LobbyServer(duel_engine=Engine())
    conn = PlayerConnection.__new__(PlayerConnection)
    conn.name = "Player"
    conn.slot = 0
    conn.ready = False
    conn.deck_main = []
    conn.deck_extra = []
    conn.deck_side = []
    conn.room = Room(1, {"no_check_deck": 1})
    conn.room.players[0] = conn

    payload = struct.pack("<II", 6, 1) + struct.pack("<IIIIII", 1, 2, 3, 4, 5, 6)
    payload += struct.pack("<I", 1)
    asyncio.run(server._handle_update_deck(conn, payload))

    assert conn.deck_main == [1, 6]
    assert conn.deck_extra == [2, 3, 4, 5]
    assert conn.deck_side == [1]


def test_an_idle_prompt_is_summarised_for_the_log():
    from server import prompt_debug

    body = bytes([MSG_SELECT_IDLECMD, 1])
    body += struct.pack("<I", 1) + struct.pack("<IBBI", 0x1234, 1, 2, 0)   # summonable
    body += struct.pack("<I", 0)                                            # spsummon
    body += struct.pack("<I", 0)                                            # repos
    body += struct.pack("<I", 0)                                            # mset
    body += struct.pack("<I", 0)                                            # sset
    body += struct.pack("<I", 1) + struct.pack("<IBBIQB", 0x5678, 1, 2, 0, 0, 0)
    body += bytes([1, 1, 0])                                                # bp, ep, shuffle

    summary = prompt_debug.summarise(MSG_SELECT_IDLECMD, body)

    assert "0x1234" in summary
    assert "0x5678" in summary
    assert "can end turn" in summary


def test_an_empty_idle_prompt_says_so():
    from server import prompt_debug

    body = bytes([MSG_SELECT_IDLECMD, 1]) + struct.pack("<IIIIII", 0, 0, 0, 0, 0, 0)
    body += bytes([0, 0, 0])

    assert prompt_debug.summarise(MSG_SELECT_IDLECMD, body) == "nothing at all"


def test_a_malformed_prompt_summary_never_raises():
    from server import prompt_debug

    assert prompt_debug.summarise(MSG_SELECT_IDLECMD, b"\x0b\x01\x00") is None
