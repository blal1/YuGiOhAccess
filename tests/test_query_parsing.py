"""The client must parse the query buffer ocgcore actually produces.

ocgcore writes one self-describing chunk per field -- [u16 size][u32 flag][value]
-- and terminates each card with a QUERY_END chunk. Until the bundled server
started sending MSG_UPDATE_DATA nothing exercised the variable length chunks, so
they were parsed against a layout the core never emits.
"""

import io
import struct

import pytest

from game.card import card_constants
from ui.duel_messages.update_data import parse_queries


def _client():
    class FakeClient:
        read_u8 = staticmethod(lambda buf: struct.unpack("<B", buf.read(1))[0])
        read_u16 = staticmethod(lambda buf: struct.unpack("<H", buf.read(2))[0])
        read_u32 = staticmethod(lambda buf: struct.unpack("<I", buf.read(4))[0])
        read_u64 = staticmethod(lambda buf: struct.unpack("<Q", buf.read(8))[0])

    return FakeClient()


def _chunk(flag, payload):
    """One ocgcore query chunk: size counts the flag word plus the payload."""
    return struct.pack("<H", 4 + len(payload)) + struct.pack("<I", int(flag)) + payload


def _loc_info(controller, location, sequence, position):
    return struct.pack("<BBII", controller, location, sequence, position)


END = _chunk(card_constants.QUERY.END, b"")


def _parse(buffer, controller=0, location=card_constants.LOCATION.MONSTER_ZONE):
    return parse_queries(_client(), controller, location, len(buffer), io.BytesIO(buffer))


def test_fixed_size_chunks_round_trip():
    buffer = (
        _chunk(card_constants.QUERY.CODE, struct.pack("<I", 12345))
        + _chunk(card_constants.QUERY.POSITION, struct.pack("<I", int(card_constants.POSITION.FACE_UP_ATTACK)))
        + _chunk(card_constants.QUERY.ATTACK, struct.pack("<I", 1800))
        + _chunk(card_constants.QUERY.IS_PUBLIC, struct.pack("<B", 1))
        + END
    )

    queries = _parse(buffer)

    assert len(queries) == 1
    assert queries[0].code == 12345
    assert queries[0].attack == 1800
    assert queries[0].is_public == 1
    assert queries[0].controller == 0
    assert queries[0].sequence == 0


def test_race_is_a_little_endian_u64():
    # ocgcore writes the race as one uint64; reading the halves the wrong way
    # round turned every race into a nonsense value.
    buffer = _chunk(card_constants.QUERY.RACE, struct.pack("<Q", 0x40)) + END

    queries = _parse(buffer)

    assert queries[0].race == 0x40


def test_reason_card_chunk():
    payload = _loc_info(1, int(card_constants.LOCATION.GRAVE), 3, 4)
    buffer = _chunk(card_constants.QUERY.REASON_CARD, payload) + END

    queries = _parse(buffer)

    assert queries[0].reason_card == {
        "controler": 1,
        "location": int(card_constants.LOCATION.GRAVE),
        "sequence": 3,
        "position": 4,
    }


def test_reason_card_chunk_when_there_is_none():
    # The core writes ten zero bytes when the card has no reason card.
    buffer = _chunk(card_constants.QUERY.REASON_CARD, b"\x00" * 10) + END

    queries = _parse(buffer)

    assert queries[0].reason_card == {}


def test_equip_card_chunk():
    payload = _loc_info(0, int(card_constants.LOCATION.MONSTER_ZONE), 2, 1)
    buffer = _chunk(card_constants.QUERY.EQUIP_CARD, payload) + END

    queries = _parse(buffer)

    assert queries[0].equip_card["sequence"] == 2


def test_target_card_chunk():
    payload = struct.pack("<I", 2)
    payload += _loc_info(0, int(card_constants.LOCATION.MONSTER_ZONE), 1, 1)
    payload += _loc_info(1, int(card_constants.LOCATION.SPELL_AND_TRAP_ZONE), 4, 8)
    buffer = _chunk(card_constants.QUERY.TARGET_CARD, payload) + END

    queries = _parse(buffer)

    assert queries[0].target_cards == [
        (0, int(card_constants.LOCATION.MONSTER_ZONE), 1, 1),
        (1, int(card_constants.LOCATION.SPELL_AND_TRAP_ZONE), 4, 8),
    ]


def test_overlay_card_chunk():
    payload = struct.pack("<I", 2) + struct.pack("<I", 111) + struct.pack("<I", 222)
    buffer = _chunk(card_constants.QUERY.OVERLAY_CARD, payload) + END

    queries = _parse(buffer)

    assert queries[0].overlay_cards == [111, 222]


def test_counters_chunk():
    payload = struct.pack("<I", 1) + struct.pack("<I", 0x0001 + (3 << 16))
    buffer = _chunk(card_constants.QUERY.COUNTERS, payload) + END

    queries = _parse(buffer)

    assert queries[0].counters == [0x0001 + (3 << 16)]


def test_empty_zone_is_one_zero_length_chunk():
    buffer = struct.pack("<H", 0) + _chunk(card_constants.QUERY.CODE, struct.pack("<I", 7)) + END

    queries = _parse(buffer)

    assert len(queries) == 2
    assert queries[0].onfield_skipped is True
    assert queries[1].code == 7


def test_a_chunk_whose_size_lies_is_rejected():
    buffer = struct.pack("<H", 99) + struct.pack("<I", int(card_constants.QUERY.CODE)) + struct.pack("<I", 1) + END

    with pytest.raises(RuntimeError):
        _parse(buffer)
