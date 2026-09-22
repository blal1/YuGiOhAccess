"""Tests for the duel messages that had no handler at all, plus the id table.

These are the messages listed as missing protocol coverage: MSG_RELOAD_FIELD,
MSG_PLAYER_HINT, MSG_MISSED_EFFECT, MSG_SWAP_GRAVE_DECK, MSG_SHUFFLE_SET_CARD,
MSG_ROCK_PAPER_SCISSORS, MSG_HAND_RES, MSG_TAG_SWAP, MSG_SHOW_HINT, MSG_AI_NAME
and MSG_MATCH_KILL, together with the STOC packets WATCH_CHANGE and CATCHUP.
"""

import struct
from unittest.mock import MagicMock

import pytest


class NamedCard:
    def __init__(self, code):
        self.code = code
        self.controller = 0
        self.location = 0
        self.sequence = 0
        self.position = 0
        self.effect_description = ""

    def get_name(self):
        return f"Card {self.code}"

    def get_effect_description(self, description, existing=False):
        return f"effect {description}"

    def set_location_and_position_info(self, controller, location, sequence, position):
        self.controller = controller
        self.location = location
        self.sequence = sequence
        self.position = position


def _client(mocker, player_id=0):
    """A client whose read helpers follow the real unsigned little endian format."""
    client = MagicMock()
    client.what_player_am_i = player_id
    client.read_u8 = lambda buf: struct.unpack("<B", buf.read(1))[0]
    client.read_u16 = lambda buf: struct.unpack("<H", buf.read(2))[0]
    client.read_u32 = lambda buf: struct.unpack("<I", buf.read(4))[0]
    client.read_u64 = lambda buf: struct.unpack("<Q", buf.read(8))[0]
    client.read_location = lambda buf: (
        client.read_u8(buf),
        client.read_u8(buf),
        client.read_u32(buf),
        client.read_u32(buf),
    )
    mocker.patch("core.utils.output")
    stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=stack)
    return client, stack


def _outputs():
    from core import utils

    return [call.args[0] for call in utils.output.call_args_list]


def _loc_info(controller=0, location=4, sequence=0, position=1):
    return (
        struct.pack("<B", controller)
        + struct.pack("<B", location)
        + struct.pack("<I", sequence)
        + struct.pack("<I", position)
    )


# --------------------------------------------------------------- id table ----

def test_message_constants_match_the_header_when_it_is_available(tmp_path):
    """The checked-in table must be exactly what the generator produces."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    header = root / "build" / "ocgcore" / "source" / "ocgapi_constants.h"
    if not header.exists():
        pytest.skip("ocgcore sources are not checked out")

    sys.path.insert(0, str(root / "scripts"))
    try:
        import generate_message_constants as generator
    finally:
        sys.path.pop(0)

    rendered = generator.render(generator.parse_header(header))
    current = (root / "src" / "game" / "edo" / "message_constants.py").read_text(encoding="utf-8")
    assert current == rendered, "run python scripts/generate_message_constants.py"


def test_server_uses_the_generated_ids():
    """The server must not keep its own copy of the id table."""
    from game.edo import message_constants, message_routing
    from server import duel

    # Per-player routing now lives in message_routing, shared with the client.
    assert message_constants.MSG_SELECT_COUNTER in message_routing.PROMPT_MESSAGES
    assert message_constants.MSG_SORT_CARD in message_routing.PROMPT_MESSAGES
    assert message_constants.MSG_SELECT_COUNTER == 22
    assert message_constants.MSG_SORT_CARD == 25
    assert duel.PROMPT_MESSAGES is message_routing.PROMPT_MESSAGES
    assert duel.MSG_SHUFFLE_HAND == message_constants.MSG_SHUFFLE_HAND == 33
    assert duel.MSG_SWAP_GRAVE_DECK == message_constants.MSG_SWAP_GRAVE_DECK == 35
    assert duel.MSG_SHUFFLE_SET_CARD == message_constants.MSG_SHUFFLE_SET_CARD == 36
    assert duel.MSG_CONFIRM_CARDS == message_constants.MSG_CONFIRM_CARDS == 31
    # MSG_SUMMONING is 60; the old table gave that number to MSG_SWAP_GRAVE_DECK.
    assert message_constants.MSG_SUMMONING == 60


# ----------------------------------------------------------- reload field ----

def _reload_side(lp, monsters, spells, counts):
    payload = struct.pack("<I", lp)
    for sequence in range(7):
        if sequence in monsters:
            payload += struct.pack("<B", 1) + struct.pack("<B", 1) + struct.pack("<I", 0)
        else:
            payload += struct.pack("<B", 0)
    for sequence in range(8):
        if sequence in spells:
            payload += struct.pack("<B", 1) + struct.pack("<B", 1) + struct.pack("<I", 0)
        else:
            payload += struct.pack("<B", 0)
    for value in counts:
        payload += struct.pack("<I", value)
    return payload


def test_reload_field_resyncs_and_announces(mocker):
    from ui.duel_messages import reload_field

    client, _stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field
    client.player = MagicMock()
    mocker.patch("ui.duel_messages.reload_field.Card", NamedCard)

    payload = b"\xa2" + struct.pack("<I", 0)
    payload += _reload_side(7000, {0, 1}, {2}, (30, 5, 4, 1, 12, 0))
    payload += _reload_side(4500, {3}, set(), (25, 3, 9, 2, 10, 1))
    payload += struct.pack("<I", 1)
    payload += struct.pack("<I", 4242) + _loc_info() + struct.pack("<B", 0) + struct.pack("<B", 4)
    payload += struct.pack("<I", 0) + struct.pack("<Q", 7)

    reload_field.msg_reload_field(client, payload, len(payload))

    field.reset_field.assert_called_once()
    client.player.update_lifepoints.assert_any_call(7000)
    client.player.update_lifepoints.assert_any_call(4500, True)
    # The reloaded chain is the chain that is resolving, so it lands on the
    # chain stack; the chain options we may have been offered are gone.
    assert len(client.player.chain_stack) == 1
    assert client.player.chaining_cards == []

    said = "\n".join(_outputs())
    assert "Field resynchronised." in said
    assert "7000 life points" in said
    assert "4500 life points" in said
    assert "2 monsters" in said
    assert "Chain of 1 still resolving." in said


def test_reload_field_survives_a_missing_field(mocker):
    from ui.duel_messages import reload_field

    client, _stack = _client(mocker)
    client.get_duel_field.return_value = None
    client.player = None

    payload = b"\xa2" + struct.pack("<I", 0)
    payload += _reload_side(8000, set(), set(), (40, 5, 0, 0, 15, 0))
    payload += _reload_side(8000, set(), set(), (40, 5, 0, 0, 15, 0))
    payload += struct.pack("<I", 0)

    reload_field.msg_reload_field(client, payload, len(payload))
    assert any("Field resynchronised." in text for text in _outputs())


# ------------------------------------------------------------ player hint ----

def test_player_hint_tracks_effects_per_player(mocker):
    from ui.duel_messages import player_hint

    client, _stack = _client(mocker)
    player_hint.reset_player_hints()
    mocker.patch("ui.duel_messages.player_hint.describe_effect", return_value="Cannot special summon.")

    add = b"\xa5" + struct.pack("<B", 0) + struct.pack("<B", player_hint.PHINT_DESC_ADD) + struct.pack("<Q", 20000)
    player_hint.msg_player_hint(client, add, len(add))
    assert player_hint.get_player_hints(0) == ["Cannot special summon."]
    assert any("New effect on you" in text for text in _outputs())

    remove = b"\xa5" + struct.pack("<B", 0) + struct.pack("<B", player_hint.PHINT_DESC_REMOVE) + struct.pack("<Q", 20000)
    player_hint.msg_player_hint(client, remove, len(remove))
    assert player_hint.get_player_hints(0) == []
    assert any("Effect on you ended" in text for text in _outputs())


def test_player_hint_text_covers_both_players(mocker):
    from ui.duel_messages import player_hint

    client, _stack = _client(mocker)
    player_hint.reset_player_hints()
    assert "No effects" in player_hint.get_player_hints_text(client)

    player_hint.get_player_hints(0)
    player_hint._player_hints[0] = ["Yours"]
    player_hint._player_hints[1] = ["Theirs"]
    text = player_hint.get_player_hints_text(client)
    assert "Applying to you:" in text and "Yours" in text
    assert "Applying to your opponent:" in text and "Theirs" in text
    player_hint.reset_player_hints()


def test_player_hint_ignores_unknown_types(mocker):
    from ui.duel_messages import player_hint

    client, _stack = _client(mocker)
    player_hint.reset_player_hints()
    mocker.patch("ui.duel_messages.player_hint.describe_effect", return_value="Something")

    data = b"\xa5" + struct.pack("<B", 1) + struct.pack("<B", 3) + struct.pack("<Q", 1)
    player_hint.msg_player_hint(client, data, len(data))
    assert _outputs() == []


# ---------------------------------------------------------- missed effect ----

def test_missed_effect_names_the_card(mocker):
    from ui.duel_messages import missed_effect

    client, _stack = _client(mocker)
    mocker.patch("ui.duel_messages.missed_effect.Card", NamedCard)
    zone = MagicMock()
    zone.to_human_readable.return_value = "your monster zone 1"
    mocker.patch(
        "ui.duel_messages.missed_effect.LocationConversion.from_card_location",
        return_value=zone,
    )

    data = b"\x78" + _loc_info(controller=0) + struct.pack("<I", 555)
    missed_effect.msg_missed_effect(client, data, len(data))

    said = _outputs()[0]
    assert "Card 555" in said and "missed its timing" in said
    assert "your monster zone 1" in said


# -------------------------------------------------------- swap grave deck ----

def test_swap_grave_deck_drops_the_stale_graveyard(mocker):
    from ui.duel_messages import swap_grave_deck

    client, stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field

    data = b"\x23" + struct.pack("<B", 0) + struct.pack("<I", 2) + struct.pack("<I", 1) + b"\x03"
    swap_grave_deck.msg_swap_grave_deck(client, data, len(data))

    field.clear_player_graveyard.assert_called_once()
    stack.play_duel_sound_effect.assert_called_with("shuffle")
    said = _outputs()[0]
    assert "Your deck and graveyard were swapped." in said
    assert "2 extra deck monster(s)" in said


def test_swap_grave_deck_for_the_opponent(mocker):
    from ui.duel_messages import swap_grave_deck

    client, _stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field

    data = b"\x23" + struct.pack("<B", 1) + struct.pack("<I", 0) + struct.pack("<I", 0)
    swap_grave_deck.msg_swap_grave_deck(client, data, len(data))

    field.clear_opponent_graveyard.assert_called_once()
    assert "Your opponent's deck and graveyard were swapped." in _outputs()[0]


# ------------------------------------------------------- shuffle set card ----

def test_shuffle_set_card_names_the_affected_zones(mocker):
    from game.card import card_constants
    from ui.duel_messages import shuffle_set_card

    client, stack = _client(mocker)
    converted = MagicMock()
    converted.to_human_readable.return_value = "your spell and trap zone 1"
    mocker.patch("ui.duel_messages.shuffle_set_card.LocationConversion", return_value=converted)

    zone = _loc_info(controller=0, location=int(card_constants.LOCATION.SPELL_AND_TRAP_ZONE))
    data = (
        b"\x24"
        + struct.pack("<B", int(card_constants.LOCATION.SPELL_AND_TRAP_ZONE))
        + struct.pack("<B", 2)
        + zone * 4
    )
    shuffle_set_card.msg_shuffle_set_card(client, data, len(data))

    said = _outputs()[0]
    assert "2 set card(s) were shuffled" in said
    assert "your spell and trap zone 1" in said
    stack.play_duel_sound_effect.assert_called_with("shuffle")


def test_shuffle_set_card_without_a_destination_block(mocker):
    from game.card import card_constants
    from ui.duel_messages import shuffle_set_card

    client, _stack = _client(mocker)
    zone = _loc_info(controller=0, location=int(card_constants.LOCATION.MONSTER_ZONE))
    data = (
        b"\x24"
        + struct.pack("<B", int(card_constants.LOCATION.MONSTER_ZONE))
        + struct.pack("<B", 1)
        + zone
    )
    shuffle_set_card.msg_shuffle_set_card(client, data, len(data))
    assert any("set card(s) were shuffled" in text for text in _outputs())


# -------------------------------------------------- rock paper scissors -----

def test_rock_paper_scissors_prompts_only_the_asked_player(mocker):
    from ui.duel_messages import rock_paper_scissors

    client, stack = _client(mocker, player_id=0)
    menu = MagicMock()
    mocker.patch("ui.duel_messages.rock_paper_scissors.HorizontalMenu", return_value=menu)

    data = b"\x84" + struct.pack("<B", 0)
    rock_paper_scissors.msg_rock_paper_scissors(client, data, len(data))
    stack.push_ui.assert_called_once_with(menu)

    stack.push_ui.reset_mock()
    data = b"\x84" + struct.pack("<B", 1)
    rock_paper_scissors.msg_rock_paper_scissors(client, data, len(data))
    stack.push_ui.assert_not_called()
    assert any("opponent is choosing" in text for text in _outputs())


def test_send_hand_answers_with_an_int(mocker):
    from game.edo import structs
    from ui.duel_messages import rock_paper_scissors

    client, stack = _client(mocker)
    rock_paper_scissors.send_hand(client, rock_paper_scissors.ROCK)
    stack.pop_ui.assert_called_once()
    client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("<i", 2))


@pytest.mark.parametrize(
    "hand0,hand1,expected",
    [
        (2, 1, "You won."),      # rock beats scissors
        (1, 2, "You lost."),     # scissors lose to rock
        (3, 3, "It's a tie."),
    ],
)
def test_hand_res_reports_the_outcome(mocker, hand0, hand1, expected):
    from ui.duel_messages import rock_paper_scissors

    client, _stack = _client(mocker, player_id=0)
    data = b"\x85" + struct.pack("<B", hand0 | (hand1 << 2))
    rock_paper_scissors.msg_hand_res(client, data, len(data))
    assert expected in _outputs()[0]


def test_hand_res_is_read_from_the_second_player_seat(mocker):
    from ui.duel_messages import rock_paper_scissors

    client, _stack = _client(mocker, player_id=1)
    # player 0 threw scissors, player 1 (us) threw rock: we win.
    data = b"\x85" + struct.pack("<B", 1 | (2 << 2))
    rock_paper_scissors.msg_hand_res(client, data, len(data))
    assert "You won." in _outputs()[0]


# ----------------------------------------------------------------- tag swap --

def test_tag_swap_replaces_the_hand(mocker):
    from ui.duel_messages import tag_swap

    client, _stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field
    mocker.patch("ui.duel_messages.tag_swap.Card", NamedCard)

    data = b"\xa1" + struct.pack("<B", 0)
    data += struct.pack("<I", 30) + struct.pack("<I", 2) + struct.pack("<I", 0) + struct.pack("<I", 2)
    data += struct.pack("<I", 0)
    data += struct.pack("<I", 11) + struct.pack("<I", 1)
    data += struct.pack("<I", 12) + struct.pack("<I", 1)
    data += struct.pack("<I", 21) + struct.pack("<I", 1)
    data += struct.pack("<I", 22) + struct.pack("<I", 1)

    tag_swap.msg_tag_swap(client, data, len(data))

    field.clear_player_hand.assert_called_once()
    assert field.append_card_to_player_hand.call_count == 2
    said = _outputs()[0]
    assert "Your tag partner takes over." in said
    assert "2 card(s) in hand, 30 in deck, 2 in extra deck." in said
    assert "Card 11" in said and "Card 12" in said


def test_tag_swap_for_the_opponent_does_not_read_their_hand(mocker):
    from ui.duel_messages import tag_swap

    client, _stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field
    mocker.patch("ui.duel_messages.tag_swap.Card", NamedCard)

    data = b"\xa1" + struct.pack("<B", 1)
    data += struct.pack("<I", 30) + struct.pack("<I", 0) + struct.pack("<I", 0) + struct.pack("<I", 1)
    data += struct.pack("<I", 0)
    data += struct.pack("<I", 11) + struct.pack("<I", 1)

    tag_swap.msg_tag_swap(client, data, len(data))

    field.clear_opponent_hand.assert_called_once()
    field.append_card_to_player_hand.assert_not_called()
    said = _outputs()[0]
    assert "Your opponent's tag partner takes over." in said
    assert "Card 11" not in said


# ---------------------------------------------------------- hints and names --

def test_show_hint_reads_the_script_text(mocker):
    from ui.duel_messages import show_hint

    client, _stack = _client(mocker)
    text = "Attack with the monster on the left.".encode("utf-8")
    data = b"\xa4" + struct.pack("<H", len(text)) + text + b"\x00"
    show_hint.msg_show_hint(client, data, len(data))
    assert "Attack with the monster on the left." in _outputs()[0]


def test_ai_name_is_remembered(mocker):
    from ui.duel_messages import show_hint

    client, _stack = _client(mocker)
    client.memory = MagicMock()
    name = "Tetsu Trudge".encode("utf-8")
    data = b"\xa3" + struct.pack("<H", len(name)) + name + b"\x00"
    show_hint.msg_ai_name(client, data, len(data))
    assert client.memory.ai_name == "Tetsu Trudge"
    assert "Tetsu Trudge" in _outputs()[0]


def test_empty_show_hint_says_nothing(mocker):
    from ui.duel_messages import show_hint

    client, _stack = _client(mocker)
    data = b"\xa4" + struct.pack("<H", 0) + b"\x00"
    show_hint.msg_show_hint(client, data, len(data))
    assert _outputs() == []


# ---------------------------------------------------------------- match kill --

def test_match_kill_names_the_card(mocker):
    from ui.duel_messages import match_kill

    client, _stack = _client(mocker)
    mocker.patch("ui.duel_messages.match_kill.Card", NamedCard)
    data = b"\xaa" + struct.pack("<I", 44508125)
    match_kill.msg_match_kill(client, data, len(data))
    assert "ended the entire match" in _outputs()[0]


# ------------------------------------------------------------ legacy messages -

def test_unequip_names_the_card(mocker):
    from ui.duel_messages import legacy_messages

    client, _stack = _client(mocker)
    client.get_card.return_value = NamedCard(9)
    data = b"\x5f" + _loc_info()
    legacy_messages.msg_unequip(client, data, len(data))
    assert "Card 9 is no longer equipped." in _outputs()[0]


def test_be_chain_target_is_announced(mocker):
    from ui.duel_messages import legacy_messages

    client, _stack = _client(mocker)
    legacy_messages.msg_be_chain_target(client, b"\x79", 1)
    assert "became a chain target" in _outputs()[0]


def test_bookkeeping_messages_are_silent(mocker):
    from ui.duel_messages import legacy_messages

    client, _stack = _client(mocker)
    legacy_messages.msg_relation(client, b"\x7a", 1)
    legacy_messages.msg_deck_bookkeeping(client, b"\x08", 1)
    legacy_messages.msg_custom(client, b"\xb4payload", 8)
    assert _outputs() == []


# ------------------------------------------------------------- chain context --

def test_chain_links_announce_what_they_answer(mocker):
    from ui.duel_messages import chaining

    client, _stack = _client(mocker)
    client.player = MagicMock()
    client.player.chain_stack = []
    mocker.patch("ui.duel_messages.chaining.Card", NamedCard)

    def link(code, size):
        return (
            b"\x46"
            + struct.pack("<I", code)
            + _loc_info()
            + struct.pack("<B", 0)
            + struct.pack("<B", 4)
            + struct.pack("<I", 0)
            + struct.pack("<Q", 1)
            + struct.pack("<I", size)
        )

    chaining.msg_chaining(client, link(1, 1), 0)
    chaining.msg_chaining(client, link(2, 2), 0)

    said = _outputs()
    assert "Chain link 1" in said[0]
    assert "Responding to" not in said[0]
    assert "Chain link 2" in said[1]
    assert "Responding to Card 1." in said[1]
    assert len(client.player.chain_stack) == 2

    text = chaining.chain_stack_text(client)
    assert "Chain of 2:" in text and "Card 1" in text and "Card 2" in text


def test_a_new_chain_restarts_the_stack(mocker):
    from ui.duel_messages import chaining

    client, _stack = _client(mocker)
    client.player = MagicMock()
    client.player.chain_stack = [NamedCard(99)]
    mocker.patch("ui.duel_messages.chaining.Card", NamedCard)

    data = (
        b"\x46"
        + struct.pack("<I", 7)
        + _loc_info()
        + struct.pack("<B", 0)
        + struct.pack("<B", 4)
        + struct.pack("<I", 0)
        + struct.pack("<Q", 1)
        + struct.pack("<I", 1)
    )
    chaining.msg_chaining(client, data, len(data))
    assert [card.code for card in client.player.chain_stack] == [7]


def test_chain_resolution_is_narrated(mocker):
    from ui.duel_messages import chained

    client, _stack = _client(mocker)
    client.player = MagicMock()
    client.player.chain_stack = [NamedCard(1), NamedCard(2)]

    chained.msg_chain_solving(client, b"\x48" + struct.pack("<B", 2), 2)
    chained.msg_chain_negated(client, b"\x4b" + struct.pack("<B", 1), 2)
    chained.msg_chain_disabled(client, b"\x4c" + struct.pack("<B", 2), 2)
    chained.msg_chain_end(client, b"\x4a", 1)

    said = _outputs()
    assert "Resolving chain link 2, Card 2." in said[0]
    assert "Chain link 1, Card 1, was negated." in said[1]
    assert "chain link 2, Card 2, was disabled." in said[2]
    assert "Chain of 2 finished resolving." in said[3]
    assert client.player.chain_stack == []


def test_chain_messages_survive_an_unknown_link(mocker):
    from ui.duel_messages import chained

    client, _stack = _client(mocker)
    client.player = MagicMock()
    client.player.chain_stack = []

    chained.msg_chain_negated(client, b"\x4b" + struct.pack("<B", 3), 2)
    assert "Chain link 3 was negated." in _outputs()[0]
