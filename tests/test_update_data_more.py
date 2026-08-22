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
    return struct.pack("h", len(payload) + 4) + struct.pack("I", int(flags)) + payload


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
    from game.card import card_constants
    from ui.duel_messages.update_data import parse_queries

    client = _client()
    flags = (
        card_constants.QUERY.CODE
        | card_constants.QUERY.POSITION
        | card_constants.QUERY.ALIAS
        | card_constants.QUERY.TYPE
        | card_constants.QUERY.LEVEL
        | card_constants.QUERY.RANK
        | card_constants.QUERY.ATTRIBUTE
        | card_constants.QUERY.RACE
        | card_constants.QUERY.ATTACK
        | card_constants.QUERY.DEFENSE
        | card_constants.QUERY.BASE_ATTACK
        | card_constants.QUERY.BASE_DEFENSE
        | card_constants.QUERY.REASON
        | card_constants.QUERY.COVER
        | card_constants.QUERY.REASON_CARD
        | card_constants.QUERY.EQUIP_CARD
        | card_constants.QUERY.TARGET_CARD
        | card_constants.QUERY.OVERLAY_CARD
        | card_constants.QUERY.COUNTERS
        | card_constants.QUERY.OWNER
        | card_constants.QUERY.STATUS
        | card_constants.QUERY.IS_PUBLIC
        | card_constants.QUERY.LSCALE
        | card_constants.QUERY.RSCALE
        | card_constants.QUERY.LINK
        | card_constants.QUERY.IS_HIDDEN
        | card_constants.QUERY.END
    )
    payload = b""
    for value in (100, 1, 200, 300, 4, 4, 5):
        payload += struct.pack("I", value)
    payload += struct.pack("I", 6) + struct.pack("I", 7)
    for value in (1500, 1200, 1600, 1300, 9, 10):
        payload += struct.pack("I", value)
    payload += struct.pack("h", 10) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.GRAVE) + struct.pack("I", 1) + struct.pack("I", 2)
    payload += struct.pack("h", 10) + struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", 3) + struct.pack("I", 4)
    payload += struct.pack("h", 10) + struct.pack("I", 1)
    payload += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 5) + struct.pack("I", 6)
    payload += struct.pack("h", 8) + struct.pack("I", 2) + struct.pack("I", 111) + struct.pack("I", 222)
    payload += struct.pack("h", 4) + struct.pack("I", 1) + struct.pack("I", 0x10001)
    payload += struct.pack("B", 0)
    for value in (55, 1, 2, 3, 0x20, 0x04):
        payload += struct.pack("I", value)
    payload += struct.pack("B", 1)

    chunk = struct.pack("h", 151) + struct.pack("I", int(flags)) + payload
    queries = parse_queries(client, 0, card_constants.LOCATION.MONSTER_ZONE, 153, io.BytesIO(chunk))
    assert len(queries) == 1
    q = queries[0]
    assert q.code == 100
    assert q.position == 1
    assert q.controller == 0
    assert q.location == card_constants.LOCATION.MONSTER_ZONE
    assert q.sequence == 0
    assert q.race == (6 << 32) + 7
    assert q.reason_card["location"] == card_constants.LOCATION.GRAVE
    assert q.equip_card["controler"] == 1
    assert q.target_cards == [(0, card_constants.LOCATION.MONSTER_ZONE, 5, 6)]
    assert q.overlay_cards == [111, 222]
    assert q.counters == [0x10001]
    assert q.link
    assert q.link_marker

    skipped = struct.pack("h", 0)
    queries = parse_queries(client, 0, card_constants.LOCATION.HAND, len(skipped), io.BytesIO(skipped))
    assert queries[0].onfield_skipped is True


def test_parse_queries_empty_nested_cards_and_size_error():
    from game.card import card_constants
    from ui.duel_messages.update_data import parse_queries

    client = _client()
    flags = card_constants.QUERY.REASON_CARD | card_constants.QUERY.EQUIP_CARD | card_constants.QUERY.END
    payload = struct.pack("h", 0) + struct.pack("Q", 0) + struct.pack("h", 0) + struct.pack("Q", 0)
    chunk = _query_chunk(flags, payload)
    q = parse_queries(client, 0, card_constants.LOCATION.HAND, len(chunk), io.BytesIO(chunk))[0]
    assert q.reason_card == {}
    assert q.equip_card == {}

    bad = struct.pack("h", 10) + struct.pack("I", int(card_constants.QUERY.CODE)) + struct.pack("I", 1)
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
