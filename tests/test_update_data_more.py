import io
import struct
from unittest.mock import MagicMock

import pytest


def _client():
    client = MagicMock()
    client.read_u8 = lambda buf: struct.unpack("B", buf.read(1))[0]
    client.read_u16 = lambda buf: struct.unpack("h", buf.read(2))[0]
    client.read_u32 = lambda buf: struct.unpack("I", buf.read(4))[0]
    client.read_u64 = lambda buf: struct.unpack("Q", buf.read(8))[0]
    client.turn_count = 0
    client.has_announced_turn_order = False
    return client


def _query_chunk(flags, payload):
    """One ocgcore query chunk: [u16 size][u32 flag][payload]."""
    return struct.pack("<H", len(payload) + 4) + struct.pack("<I", int(flags)) + payload


def test_query_result_dynamic_fields():
    from game.card import card_constants
    from ui.duel_messages.update_data import QueryResult

    query = QueryResult()
    assert query.flags == card_constants.QUERY(0)
    query.code = 123
    assert query.fields["code"] == 123
    assert "QueryResult" in repr(query)
    with pytest.raises(AttributeError):
        query.missing


def test_parse_queries_all_major_flags_and_skips():
    """A full card, in the one-chunk-per-field layout ocgcore emits."""
    from game.card import card_constants
    from ui.duel_messages.update_data import parse_queries

    client = _client()
    Q = card_constants.QUERY

    def loc_info(controller, location, sequence, position):
        return struct.pack("<BBII", controller, location, sequence, position)

    buffer = b""
    for flag, value in (
        (Q.CODE, 100),
        (Q.POSITION, 1),
        (Q.ALIAS, 200),
        (Q.TYPE, 300),
        (Q.LEVEL, 4),
        (Q.RANK, 4),
        (Q.ATTRIBUTE, 5),
        (Q.ATTACK, 1500),
        (Q.DEFENSE, 1200),
        (Q.BASE_ATTACK, 1600),
        (Q.BASE_DEFENSE, 1300),
        (Q.REASON, 9),
        (Q.COVER, 10),
        (Q.STATUS, 55),
    ):
        buffer += _query_chunk(flag, struct.pack("<I", value))
    buffer += _query_chunk(Q.RACE, struct.pack("<Q", 0x40))
    buffer += _query_chunk(Q.REASON_CARD, loc_info(0, int(card_constants.LOCATION.GRAVE), 1, 2))
    buffer += _query_chunk(Q.EQUIP_CARD, loc_info(1, int(card_constants.LOCATION.HAND), 3, 4))
    buffer += _query_chunk(
        Q.TARGET_CARD,
        struct.pack("<I", 1) + loc_info(0, int(card_constants.LOCATION.MONSTER_ZONE), 5, 6),
    )
    buffer += _query_chunk(Q.OVERLAY_CARD, struct.pack("<III", 2, 111, 222))
    buffer += _query_chunk(Q.COUNTERS, struct.pack("<II", 1, 0x10001))
    buffer += _query_chunk(Q.OWNER, struct.pack("<B", 0))
    buffer += _query_chunk(Q.IS_PUBLIC, struct.pack("<B", 1))
    buffer += _query_chunk(Q.LSCALE, struct.pack("<I", 2))
    buffer += _query_chunk(Q.RSCALE, struct.pack("<I", 3))
    buffer += _query_chunk(Q.LINK, struct.pack("<II", 0x20, 0x04))
    buffer += _query_chunk(Q.IS_HIDDEN, struct.pack("<B", 1))
    buffer += _query_chunk(Q.END, b"")

    queries = parse_queries(
        client, 0, card_constants.LOCATION.MONSTER_ZONE, len(buffer), io.BytesIO(buffer)
    )

    assert len(queries) == 1
    q = queries[0]
    assert q.code == 100
    assert q.position == 1
    assert q.controller == 0
    assert q.location == card_constants.LOCATION.MONSTER_ZONE
    assert q.sequence == 0
    assert q.race == 0x40
    assert q.reason_card["location"] == card_constants.LOCATION.GRAVE
    assert q.equip_card["controler"] == 1
    assert q.target_cards == [(0, card_constants.LOCATION.MONSTER_ZONE, 5, 6)]
    assert q.overlay_cards == [111, 222]
    assert q.counters == [0x10001]
    assert q.is_public == 1
    assert q.link == 0x20
    assert q.link_marker == 0x04

    skipped = struct.pack("<H", 0)
    queries = parse_queries(client, 0, card_constants.LOCATION.HAND, len(skipped), io.BytesIO(skipped))
    assert queries[0].onfield_skipped is True


def test_parse_queries_empty_nested_cards_and_size_error():
    from game.card import card_constants
    from ui.duel_messages.update_data import parse_queries

    client = _client()
    # The core writes ten zero bytes when there is no reason or equip card.
    buffer = _query_chunk(card_constants.QUERY.REASON_CARD, b"\x00" * 10)
    buffer += _query_chunk(card_constants.QUERY.EQUIP_CARD, b"\x00" * 10)
    buffer += _query_chunk(card_constants.QUERY.END, b"")
    q = parse_queries(client, 0, card_constants.LOCATION.HAND, len(buffer), io.BytesIO(buffer))[0]
    assert q.reason_card == {}
    assert q.equip_card == {}

    bad = struct.pack("<H", 10) + struct.pack("<I", int(card_constants.QUERY.CODE)) + struct.pack("<I", 1)
    with pytest.raises(RuntimeError):
        parse_queries(client, 0, card_constants.LOCATION.HAND, len(bad), io.BytesIO(bad))


def test_update_data_turn_order_and_msg_parser(mocker):
    from game.card import card_constants
    from ui.duel_messages import update_data

    client = _client()
    field = MagicMock()
    client.get_duel_field.return_value = field
    mocker.patch("ui.duel_messages.update_data.utils.output")
    update_data.update_data(client, 0, card_constants.LOCATION.HAND, ["q"])
    assert client.what_player_am_i == 0
    assert client.has_announced_turn_order is True
    field.update_field.assert_called_with(client, 0, card_constants.LOCATION.HAND, ["q"])

    client.turn_count = 0
    client.has_announced_turn_order = False
    update_data.update_data(client, 1, card_constants.LOCATION.HAND, ["q2"])
    assert client.what_player_am_i == 1

    payload = struct.pack("h", 0)
    data = b"\x06" + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", len(payload)) + payload
    update_data.msg_update_data(client, data, len(data))
