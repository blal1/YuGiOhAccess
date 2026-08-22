import struct
from unittest.mock import MagicMock

from tests.test_duel_messages_remaining_more import FakeCheckbox
from tests.test_duel_messages_simple_more import NamedCard, _client
from tests.test_ui_flows_more import FakeMenu


def _loc(controller=0, location=4, sequence=0, position=1):
    return (
        struct.pack("B", controller)
        + struct.pack("B", location)
        + struct.pack("I", sequence)
        + struct.pack("I", position)
    )


def test_select_card_menu_finish_cancel_and_parsers(mocker):
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import select_card

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.select_card.VerticalMenu", FakeMenu)
    mocker.patch("ui.duel_messages.select_card.wx.CheckBox", FakeCheckbox)
    loc = MagicMock()
    loc.to_human_readable.return_value = "Your monster zone 1"
    mocker.patch("ui.duel_messages.select_card.LocationConversion.from_card_location", return_value=loc)

    cards = [NamedCard("A"), NamedCard("B")]
    select_card.select_card(client, 0, True, 1, 2, cards)
    menu = stack.push_ui.call_args.args[0]
    assert any(item[0] == "Cancel" for item in menu.items)
    menu.cells = [[FakeCheckbox()], [FakeCheckbox()]]
    select_card.finish_card_selection(client, menu, cards, 1, 2, False)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1) + struct.pack("I", 2) + struct.pack("H", 0) + struct.pack("H", 1))

    select_card.cancel_card_selection(client)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 0xFFFFFFFF))

    card_cls = mocker.patch("ui.duel_messages.select_card.Card", side_effect=lambda code: NamedCard(f"Card {code}"))
    payload = b"\x0f" + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("I", 1) + struct.pack("I", 1) + struct.pack("I", 2)
    payload += struct.pack("I", 123) + _loc(0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK)
    payload += struct.pack("I", 0) + _loc(0, card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 1, card_constants.POSITION.FACE_DOWN)
    select_card.msg_select_card(client, payload, len(payload))
    assert card_cls.call_count >= 2

    tribute = b"\x14" + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("I", 1) + struct.pack("I", 1) + struct.pack("I", 1)
    tribute += struct.pack("I", 321) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("B", 1)
    select_card.msg_select_tribute(client, tribute, len(tribute))


def test_select_unselect_card_menu_and_parser(mocker):
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import select_unselect_card

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.select_unselect_card.VerticalMenu", FakeMenu)
    loc = MagicMock()
    loc.to_human_readable.return_value = "Your hand 1"
    mocker.patch("ui.duel_messages.select_unselect_card.LocationConversion.from_card_location", return_value=loc)
    card_cls = mocker.patch("ui.duel_messages.select_unselect_card.Card", side_effect=lambda code: NamedCard(f"Card {code}"))

    select_cards = [NamedCard("A")]
    unselect_cards = [NamedCard("B")]
    select_unselect_card.select_unselect_card(client, 0, True, True, 1, 2, select_cards, unselect_cards)
    menu = stack.push_ui.call_args.args[0]
    assert any("Finish" in item[0] for item in menu.items)
    select_unselect_card.select_unselect_specific_card(client, 1)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1) + struct.pack("I", 1))
    select_unselect_card.select_unselect_specific_card(client, -1)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("i", -1))

    data = b"\x1a" + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("B", 0)
    data += struct.pack("I", 1) + struct.pack("I", 2)
    data += struct.pack("I", 1) + struct.pack("I", 100) + _loc(0, card_constants.LOCATION.HAND, 0, 1)
    data += struct.pack("I", 1) + struct.pack("I", 200) + _loc(0, card_constants.LOCATION.HAND, 1, 1)
    select_unselect_card.msg_select_unselect_card(client, data + b"left", len(data) + 4)
    assert card_cls.call_count >= 2


def test_battle_extra_deck_and_flip_handlers(mocker):
    from game.card import card_constants
    from ui.duel_messages import damage_step_battle, extra_deck_top, flip_summoning

    client, _stack = _client(mocker)
    attacker = NamedCard("Attacker", card_type=card_constants.TYPE.LINK)
    target = NamedCard("Target")
    client.get_card.side_effect = [attacker, attacker, target]
    damage_step_battle.damage_step_battle(
        client,
        0,
        card_constants.LOCATION.MONSTER_ZONE,
        0,
        1,
        2000,
        0,
        0,
        1,
        card_constants.LOCATION.MONSTER_ZONE,
        1,
        1,
        1500,
        1200,
        0,
    )
    damage_step_battle.damage_step_battle(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 1, 2000, 1000, 0, 0, 0, 0, 0, 0, 0, 0)

    card_cls = mocker.patch("ui.duel_messages.extra_deck_top.Card", side_effect=lambda code: NamedCard(f"Extra {code}"))
    extra_deck_top.confirm_extra_decktop(client, 0, [NamedCard("A")])
    extra_deck_top.confirm_extra_decktop(client, 1, [NamedCard("B")])
    data = b"\x2a" + struct.pack("B", 0) + struct.pack("I", 1)
    data += struct.pack("I", 123 | 0x80000000) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.EXTRA) + struct.pack("I", 0)
    extra_deck_top.msg_confirm_extra_decktop(client, data, len(data))
    assert card_cls.called

    flip_summoning.flipsummoning(client, "unknown", 0, card_constants.LOCATION.MONSTER_ZONE, 0, 1)
    faceup = NamedCard("Flip")
    faceup.controller = 0
    flip_summoning.flipsummoning(client, faceup, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 1)
    faceup.controller = 1
    flip_summoning.flipsummoning(client, faceup, 1, card_constants.LOCATION.MONSTER_ZONE, 0, 1)
    client.get_card.return_value = faceup
    client.get_card.side_effect = None
    data = b"\x40" + struct.pack("I", 1) + _loc(0, card_constants.LOCATION.MONSTER_ZONE, 0, 1)
    flip_summoning.msg_flipsummoning(client, data, len(data))
    flip_summoning.msg_flipsummoned(client, b"\x41abc", 4)
