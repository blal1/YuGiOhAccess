"""Two things that went wrong once a duel stopped being normal.

* An empty zone holds its own label ("Empty Monster 1") where a card would be,
  so anything that asked the field for a card could get a string back and then
  try to use it as one.
* The core kept asking for decisions after it had announced a winner. The
  client had already forgotten which side it was, so it cancelled every prompt,
  which produced another winner announcement, and round it went.
"""

import asyncio
from types import SimpleNamespace


from game.edo.message_constants import MSG_SELECT_IDLECMD, MSG_WIN
from server.protocol import ServerPacket, RoomState


# ------------------------------------------------------------- empty zones --

class FakeZone:
    def __init__(self, card):
        self.card = card


def _client_with_zones(zones):
    from game.client import Client

    client = Client.__new__(Client)
    client._what_player_am_i = 0
    client.duel_field = SimpleNamespace(zones=zones)
    return client


def test_an_empty_zone_does_not_look_like_a_card(mocker):
    from game.card.location_conversion import LocationConversion

    mocker.patch.object(LocationConversion, "to_zone_key", return_value="pm0")
    client = _client_with_zones({"pm0": FakeZone("Empty Monster 1")})

    assert client.get_card(0, 4, 0, max_retries=1, base_delay=0) is None


def test_a_real_card_is_still_returned(mocker):
    from game.card.card import Card
    from game.card.location_conversion import LocationConversion

    mocker.patch.object(LocationConversion, "to_zone_key", return_value="pm0")
    card = Card(0)
    client = _client_with_zones({"pm0": FakeZone(card)})

    assert client.get_card(0, 4, 0, max_retries=1, base_delay=0) is card


def test_asking_for_a_card_with_no_field_does_not_explode(mocker):
    from game.card.location_conversion import LocationConversion
    from game.client import Client

    mocker.patch.object(LocationConversion, "to_zone_key", return_value="pm0")
    client = Client.__new__(Client)
    client._what_player_am_i = 0
    client.duel_field = None

    assert client.get_card(0, 4, 0, max_retries=1, base_delay=0) is None


# --------------------------------------------------------- the duel ending --

class FakeConn:
    def __init__(self, name, slot):
        self.name, self.slot = name, slot
        self.deck_main, self.deck_extra = [1], []
        self.sent = []

    async def send(self, packet_id, data=b""):
        self.sent.append((packet_id, data))

    def game_messages(self):
        return [d for p, d in self.sent if p == ServerPacket.GAME_MSG]


class FakeEngine:
    def __init__(self):
        self.responses = []
        self.destroyed = False
        self.processed = 0

    def process(self, handle):
        self.processed += 1
        return 1  # AWAITING

    def get_message(self, handle):
        return b""

    def set_response(self, handle, payload):
        self.responses.append(payload)

    def destroy_duel(self, handle):
        self.destroyed = True

    def query_location(self, *args):
        return b""


def _duel():
    from server.duel import DuelInstance

    # The real Room, not a stand-in: it is a plain object with no I/O, and a
    # hand written copy of its fields goes stale every time one is added.
    from server.lobby import Room

    room = Room(1, {})
    room.players = [FakeConn("Player", 0), FakeConn("WindBot", 1)]
    room.state = RoomState.DUELING

    async def broadcast(packet_id, data=b"", exclude=None):
        for conn in room.players:
            if conn is not exclude:
                await conn.send(packet_id, data)

    async def broadcast_players(packet_id, data=b""):
        for conn in room.players:
            await conn.send(packet_id, data)

    room.broadcast = broadcast
    room.broadcast_players = broadcast_players
    duel = DuelInstance(room, FakeEngine())
    duel._duel_handle = 1
    duel.set_first_player_slot(0)
    return duel, room


def test_a_winner_ends_the_duel():
    duel, room = _duel()

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 1])))

    assert duel.is_finished
    assert duel.engine.destroyed
    assert any(p == ServerPacket.DUEL_END for p, _d in room.players[0].sent)


def test_no_prompt_is_sent_once_a_winner_is_known():
    duel, room = _duel()
    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 1])))
    before = len(room.players[0].game_messages())

    asyncio.run(duel._send_game_message(MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0]) + b"\x00"))

    assert len(room.players[0].game_messages()) == before


def test_a_response_after_the_duel_is_ignored():
    duel, room = _duel()
    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 1])))

    asyncio.run(duel.handle_response(room.players[0], b"\xff\xff\xff\xff"))

    assert duel.engine.responses == []


def test_the_winner_is_announced_to_both_players():
    duel, room = _duel()

    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 1])))

    for player in room.players:
        assert bytes([MSG_WIN, 0, 1]) in player.game_messages()


def test_the_engine_is_not_asked_to_carry_on_after_a_win():
    duel, room = _duel()
    asyncio.run(duel._send_game_message(MSG_WIN, bytes([MSG_WIN, 0, 1])))
    processed = duel.engine.processed

    asyncio.run(duel._process_loop())

    assert duel.engine.processed == processed


# ------------------------------------------------- the field after the duel --

def test_walking_the_board_after_the_duel_does_not_crash(mocker):
    from game.card.card import Card
    from ui import duel_field

    field = duel_field.DuelField.__new__(duel_field.DuelField)
    field.client = SimpleNamespace(player=None, what_player_am_i=0)

    assert field.resolve_labels_for_card(Card(0)) == ""
