"""Nobody may read the other duelist's private cards off the wire.

ocgcore answers every query and writes every message with full knowledge, so
these tests pin down what the server strips before each copy leaves the room.
"""

import asyncio
import struct
from types import SimpleNamespace

import pytest

from game.card import card_constants
from game.edo.message_constants import (
    MSG_DRAW,
    MSG_MOVE,
    MSG_SELECT_IDLECMD,
    MSG_SHUFFLE_HAND,
    MSG_UPDATE_DATA,
)
from server import visibility
from server.core import LOCATION_HAND, LOCATION_MZONE
from server.protocol import ServerPacket, RoomState

Q = card_constants.QUERY


# ------------------------------------------------------------ query buffers --

def _chunk(flag, payload):
    return struct.pack("<H", 4 + len(payload)) + struct.pack("<I", int(flag)) + payload


def _chunks(code, is_public, attack=1800):
    return (
        _chunk(Q.CODE, struct.pack("<I", code))
        + _chunk(Q.POSITION, struct.pack("<I", int(card_constants.POSITION.FACE_DOWN_DEFENSE)))
        + _chunk(Q.ATTACK, struct.pack("<I", attack))
        + _chunk(visibility.QUERY_IS_PUBLIC, struct.pack("<B", 1 if is_public else 0))
        + _chunk(Q.END, b"")
    )


def _buffer(*chunk_groups):
    """A query buffer as OCG_DuelQueryLocation returns it: length word first."""
    body = b"".join(chunk_groups)
    return struct.pack("<I", len(body)) + body


def _card(code, is_public, attack=1800):
    return _buffer(_chunks(code, is_public, attack))


def _codes(buffer):
    found = []
    for start, end, flag in visibility.iter_query_chunks(buffer, visibility.QUERY_LENGTH_PREFIX):
        if flag == int(Q.CODE):
            found.append(struct.unpack_from("<I", buffer, start + 6)[0])
    return found


def test_the_controller_sees_their_own_hidden_cards():
    buffer = _card(12345, is_public=False)

    assert _codes(visibility.redact_query_buffer(buffer, reveal=True)) == [12345]


def test_a_hidden_card_loses_its_identity_for_everyone_else():
    buffer = _card(12345, is_public=False)

    redacted = visibility.redact_query_buffer(buffer, reveal=False)

    assert _codes(redacted) == [0]
    assert len(redacted) == len(buffer)


def test_a_public_card_keeps_its_identity():
    buffer = _card(12345, is_public=True)

    assert _codes(visibility.redact_query_buffer(buffer, reveal=False)) == [12345]


def test_redaction_is_decided_per_card():
    buffer = _buffer(_chunks(111, True), _chunks(222, False), _chunks(333, True))

    assert _codes(visibility.redact_query_buffer(buffer, reveal=False)) == [111, 0, 333]


def test_stats_of_a_hidden_card_are_blanked_too():
    buffer = _card(12345, is_public=False, attack=2500)

    redacted = visibility.redact_query_buffer(buffer, reveal=False)

    attacks = [
        struct.unpack_from("<I", redacted, start + 6)[0]
        for start, end, flag in visibility.iter_query_chunks(redacted, visibility.QUERY_LENGTH_PREFIX)
        if flag == int(Q.ATTACK)
    ]
    assert attacks == [0]


def test_empty_zones_survive_redaction():
    buffer = _buffer(struct.pack("<H", 0), _chunks(12345, False), struct.pack("<H", 0))

    redacted = visibility.redact_query_buffer(buffer, reveal=False)

    assert len(redacted) == len(buffer)
    chunks = visibility.iter_query_chunks(redacted, visibility.QUERY_LENGTH_PREFIX)
    assert [flag for _s, _e, flag in chunks].count(None) == 2


# --------------------------------------------------------------- visibility --

@pytest.mark.parametrize(
    "location,position,controller,recipient,expected",
    [
        (card_constants.LOCATION.DECK, card_constants.POSITION.FACE_UP_ATTACK, 0, 0, False),
        (card_constants.LOCATION.HAND, card_constants.POSITION.FACE_DOWN_ATTACK, 0, 0, True),
        (card_constants.LOCATION.HAND, card_constants.POSITION.FACE_DOWN_ATTACK, 0, 1, False),
        (card_constants.LOCATION.GRAVE, card_constants.POSITION.FACE_UP_ATTACK, 0, 1, True),
        (card_constants.LOCATION.MONSTER_ZONE, card_constants.POSITION.FACE_DOWN_DEFENSE, 0, 1, False),
        (card_constants.LOCATION.MONSTER_ZONE, card_constants.POSITION.FACE_UP_ATTACK, 0, 1, True),
        (card_constants.LOCATION.OVERLAY, 0, 0, 1, True),
    ],
)
def test_card_visibility_rules(location, position, controller, recipient, expected):
    assert visibility.card_visible_to(recipient, controller, int(location), int(position)) is expected


# ----------------------------------------------------------------- messages --

def _loc(controller, location, sequence, position):
    return struct.pack("<BBII", controller, location, sequence, position)


def test_draw_hides_the_codes_from_the_other_player():
    msg = bytes([MSG_DRAW, 0]) + struct.pack("<I", 2)
    msg += struct.pack("<II", 111, int(card_constants.POSITION.FACE_DOWN_ATTACK))
    msg += struct.pack("<II", 222, int(card_constants.POSITION.FACE_DOWN_ATTACK))

    assert visibility.redact_message(MSG_DRAW, msg, 0) == msg
    hidden = visibility.redact_message(MSG_DRAW, msg, 1)
    assert struct.unpack_from("<I", hidden, 6)[0] == 0
    assert struct.unpack_from("<I", hidden, 14)[0] == 0
    assert len(hidden) == len(msg)


def test_shuffle_hand_hides_the_codes_from_the_other_player():
    msg = bytes([MSG_SHUFFLE_HAND, 1]) + struct.pack("<I", 2) + struct.pack("<II", 111, 222)

    assert visibility.redact_message(MSG_SHUFFLE_HAND, msg, 1) == msg
    hidden = visibility.redact_message(MSG_SHUFFLE_HAND, msg, 0)
    assert struct.unpack("<II", hidden[6:14]) == (0, 0)


def test_a_set_monster_keeps_its_code_only_for_its_controller():
    msg = bytes([MSG_MOVE]) + struct.pack("<I", 12345)
    msg += _loc(0, int(card_constants.LOCATION.HAND), 0, int(card_constants.POSITION.FACE_DOWN_ATTACK))
    msg += _loc(0, int(card_constants.LOCATION.MONSTER_ZONE), 2, int(card_constants.POSITION.FACE_DOWN_DEFENSE))
    msg += struct.pack("<I", 0)

    assert visibility.redact_message(MSG_MOVE, msg, 0) == msg
    assert struct.unpack_from("<I", visibility.redact_message(MSG_MOVE, msg, 1), 1)[0] == 0


def test_a_card_sent_to_the_graveyard_stays_visible_to_both():
    msg = bytes([MSG_MOVE]) + struct.pack("<I", 12345)
    msg += _loc(0, int(card_constants.LOCATION.MONSTER_ZONE), 2, int(card_constants.POSITION.FACE_UP_ATTACK))
    msg += _loc(0, int(card_constants.LOCATION.GRAVE), 0, int(card_constants.POSITION.FACE_UP_ATTACK))
    msg += struct.pack("<I", 0)

    assert visibility.redact_message(MSG_MOVE, msg, 1) == msg


def test_move_reads_an_overlay_location_at_the_right_width():
    # An overlay reference carries no position word, so a fixed offset reader
    # would take the reason field for a position.
    msg = bytes([MSG_MOVE]) + struct.pack("<I", 12345)
    msg += struct.pack("<BBI", 0, int(card_constants.LOCATION.MONSTER_ZONE) | int(card_constants.LOCATION.OVERLAY), 1)
    msg += _loc(0, int(card_constants.LOCATION.GRAVE), 0, int(card_constants.POSITION.FACE_UP_ATTACK))
    msg += struct.pack("<I", 0)

    assert visibility.redact_message(MSG_MOVE, msg, 1) == msg


# -------------------------------------------------------------- the refresh --

class FakeConn:
    def __init__(self, name, slot):
        self.name = name
        self.slot = slot
        self.deck_main = [1]
        self.deck_extra = []
        self.sent = []

    async def send(self, packet_id, data=b""):
        self.sent.append((packet_id, data))

    def update_data_messages(self):
        return [
            data for packet_id, data in self.sent
            if packet_id == ServerPacket.GAME_MSG and data and data[0] == MSG_UPDATE_DATA
        ]


class FakeEngine:
    def __init__(self, buffers):
        self.buffers = buffers
        self.queries = []

    def query_location(self, handle, flags, controller, location):
        self.queries.append((controller, location))
        return self.buffers.get((controller, location), b"")


def _duel(engine, first_player_slot=0):
    from server.duel import DuelInstance

    room = SimpleNamespace(
        room_id=1,
        host_info={},
        players=[FakeConn("Human", 0), FakeConn("WindBot", 1)],
        observers=[],
        state=RoomState.DUELING,
    )

    async def broadcast(packet_id, data=b"", exclude=None):
        for conn in room.players:
            if conn and conn is not exclude:
                await conn.send(packet_id, data)

    room.broadcast = broadcast
    duel = DuelInstance(room, engine)
    duel._duel_handle = 1
    duel.set_first_player_slot(first_player_slot)
    return duel, room


def test_refresh_sends_update_data_for_every_rendered_location():
    from server.duel import REFRESHED_LOCATIONS

    engine = FakeEngine({(c, loc): _card(1, True) for c in (0, 1) for loc in REFRESHED_LOCATIONS})
    duel, room = _duel(engine)

    asyncio.run(duel._refresh_field())

    assert engine.queries == [(c, loc) for c in (0, 1) for loc in REFRESHED_LOCATIONS]
    assert len(room.players[0].update_data_messages()) == 2 * len(REFRESHED_LOCATIONS)


def test_each_player_gets_their_own_view_of_a_hand():
    engine = FakeEngine({(0, LOCATION_HAND): _card(12345, is_public=False)})
    duel, room = _duel(engine)

    asyncio.run(duel._refresh_field())

    # Core player 0 is room slot 0 here, so slot 0 owns this hand.
    mine = room.players[0].update_data_messages()[0]
    theirs = room.players[1].update_data_messages()[0]
    assert _codes(mine[3:]) == [12345]
    assert _codes(theirs[3:]) == [0]


def test_update_data_header_matches_what_the_client_reads():
    buffer = _card(12345, is_public=True)
    engine = FakeEngine({(1, LOCATION_MZONE): buffer})
    duel, room = _duel(engine)

    asyncio.run(duel._refresh_field())

    message = room.players[0].update_data_messages()[0]
    assert message[0] == MSG_UPDATE_DATA
    assert message[1] == 1  # controller
    assert message[2] == LOCATION_MZONE
    # The size the client reads is the core's own length word, not a second one.
    assert struct.unpack_from("<I", message, 3)[0] == len(message) - 7
    assert message[3:] == buffer


def test_a_prompt_is_preceded_by_a_refresh():
    engine = FakeEngine({(0, LOCATION_HAND): _card(1, True)})
    duel, room = _duel(engine)

    asyncio.run(duel._send_game_message(MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0]) + b"\x00"))

    kinds = [data[0] for packet_id, data in room.players[0].sent]
    assert MSG_UPDATE_DATA in kinds
    assert kinds.index(MSG_UPDATE_DATA) < kinds.index(MSG_SELECT_IDLECMD)


def test_an_observer_sees_neither_hand():
    observer = FakeConn("Watcher", -1)
    engine = FakeEngine({(0, LOCATION_HAND): _card(12345, is_public=False)})
    duel, room = _duel(engine)
    room.observers = [observer]

    asyncio.run(duel._refresh_field())

    assert _codes(observer.update_data_messages()[0][3:]) == [0]


def test_the_client_parses_what_the_server_sends(mocker):
    """Round trip: the refresh output goes through the real client handler."""
    from ui.duel_messages import update_data as update_data_module

    engine = FakeEngine({(0, LOCATION_MZONE): _card(12345, is_public=True)})
    duel, room = _duel(engine)
    asyncio.run(duel._refresh_field())
    message = room.players[0].update_data_messages()[0]

    client = SimpleNamespace(
        read_u8=staticmethod(lambda buf: struct.unpack("<B", buf.read(1))[0]),
        read_u16=staticmethod(lambda buf: struct.unpack("<H", buf.read(2))[0]),
        read_u32=staticmethod(lambda buf: struct.unpack("<I", buf.read(4))[0]),
        read_u64=staticmethod(lambda buf: struct.unpack("<Q", buf.read(8))[0]),
    )
    handled = mocker.patch.object(update_data_module, "update_data")

    update_data_module.msg_update_data(client, message, len(message))

    handled.assert_called_once()
    _client_arg, controller, location, queries = handled.call_args.args
    assert controller == 0
    assert location == LOCATION_MZONE
    assert [q.code for q in queries] == [12345]


def test_a_card_without_an_is_public_field_is_hidden(caplog):
    # Fail closed: no answer from the core means no identity on the wire.
    buffer = _buffer(_chunk(Q.CODE, struct.pack("<I", 12345)) + _chunk(Q.END, b""))

    with caplog.at_level("WARNING", logger="server.visibility"):
        redacted = visibility.redact_query_buffer(buffer, reveal=False)

    assert _codes(redacted) == [0]
    assert "QUERY_IS_PUBLIC" in caplog.text


def test_the_refresh_asks_for_is_public():
    from server.duel import REFRESH_QUERY_FLAGS

    assert REFRESH_QUERY_FLAGS & visibility.QUERY_IS_PUBLIC


def test_an_unchanged_location_is_not_sent_twice():
    engine = FakeEngine({(0, LOCATION_HAND): _card(1, True)})
    duel, room = _duel(engine)

    asyncio.run(duel._refresh_field())
    asyncio.run(duel._refresh_field())

    assert len(room.players[0].update_data_messages()) == 1


def test_a_changed_location_is_sent_again():
    engine = FakeEngine({(0, LOCATION_HAND): _card(1, True)})
    duel, room = _duel(engine)

    asyncio.run(duel._refresh_field())
    engine.buffers[(0, LOCATION_HAND)] = _card(2, True)
    asyncio.run(duel._refresh_field())

    messages = room.players[0].update_data_messages()
    assert len(messages) == 2
    assert _codes(messages[1][3:]) == [2]
