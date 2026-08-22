import struct
from unittest.mock import MagicMock

from tests.test_duel_messages_simple_more import NamedCard
from tests.test_ui_flows_more import FakeMenu, FakeStatus


class CardLike(NamedCard):
    pass


def test_action_menu_all_actions_and_send_helpers(mocker):
    from game.edo import structs
    from ui import action_menu

    mocker.patch("ui.action_menu.VerticalMenu", FakeMenu)
    mocker.patch("ui.action_menu.Card", CardLike)
    stack = MagicMock()
    mocker.patch("ui.action_menu.utils.get_ui_stack", return_value=stack)
    card = CardLike("Action")
    card.strings = {1: "first"}
    card.get_effect_description = MagicMock(return_value="desc")
    card.data = 9
    client = MagicMock()
    client.player.attackable = [card]
    client.player.activatable = [card, card]
    client.player.special_summonable = [card]
    client.player.summonable = [card]
    client.player.monster_settable = [card]
    client.player.spell_settable = [card]
    client.player.repositionable = [card]
    zone = MagicMock(card=card)

    action_menu.show_action_menu_for_zone(client, zone)
    menu = stack.push_ui.call_args.args[0]
    labels = [item[0] for item in menu.items]
    assert "Attack" in labels
    assert "Special summon" in labels
    assert "Summon" in labels
    assert "Reposition" in labels

    action_menu.send_activate(client, card, 1)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", (1 << 16) + 5))
    action_menu.send_attack(client, card)
    action_menu.send_special_summon(client, card)
    action_menu.send_summon(client, card)
    action_menu.send_monster_set(client, card)
    action_menu.send_spell_set(client, card)
    action_menu.send_reposition(client, card)
    assert client.send.call_count == 7

    action_menu.show_action_menu_for_zone(client, MagicMock(card="not-card"))
    assert stack.push_ui.call_count == 1


def test_action_menu_uses_playable_identity_and_rejects_unplayable_cards(mocker):
    from game.edo import structs
    from ui import action_menu

    mocker.patch("ui.action_menu.VerticalMenu", FakeMenu)
    mocker.patch("ui.action_menu.Card", CardLike)
    output = mocker.patch("ui.action_menu.utils.output")
    stack = MagicMock()
    mocker.patch("ui.action_menu.utils.get_ui_stack", return_value=stack)

    zone_card = CardLike("Zone")
    zone_card.code = 77
    zone_card.controller = 0
    zone_card.location = 2
    zone_card.sequence = 3
    playable = CardLike("Playable")
    playable.code = 77
    playable.controller = 0
    playable.location = 2
    playable.sequence = 3
    playable.data = 4
    playable.get_effect_description = MagicMock(return_value="usable")
    client = MagicMock()
    client.player.attackable = []
    client.player.activatable = [playable]
    client.player.special_summonable = []
    client.player.summonable = []
    client.player.monster_settable = []
    client.player.spell_settable = []
    client.player.repositionable = []

    action_menu.show_action_menu_for_zone(client, MagicMock(card=zone_card))
    menu = stack.push_ui.call_args.args[0]
    assert any("Activate effect" in item[0] for item in menu.items)
    action_menu.send_activate(client, zone_card)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 5))

    stack.push_ui.reset_mock()
    output.reset_mock()
    other_zone_card = CardLike("Other")
    other_zone_card.code = 77
    other_zone_card.controller = 0
    other_zone_card.location = 2
    other_zone_card.sequence = 4
    action_menu.show_action_menu_for_zone(client, MagicMock(card=other_zone_card))
    stack.push_ui.assert_not_called()
    output.assert_called()


def test_card_list_populate_finalize_and_key_paths(mocker):
    from ui.card_list_ui import HorizontalCardList
    import ui.card_list_ui as card_list_ui

    mocker.patch("ui.card_list_ui.Card", CardLike)
    mocker.patch("ui.card_list_ui.HorizontalMenu.__init__", return_value=None)
    mocker.patch("ui.card_list_ui.HorizontalMenu.append_item")
    mocker.patch("ui.card_list_ui.HorizontalMenu.on_key_down")
    stack = MagicMock()
    mocker.patch("ui.card_list_ui.utils.get_ui_stack", return_value=stack)
    mocker.patch("ui.card_list_ui.utils.output")
    mocker.patch("ui.card_list_ui.wx.Yield", side_effect=lambda: None)
    mocker.patch("ui.card_list_ui.wx.WXK_SPACE", 32)
    mocker.patch("ui.card_list_ui.wx.WXK_ESCAPE", 27)

    client = MagicMock()
    client.get_duel_field.return_value.resolve_labels_for_card.return_value = "Label"
    cards = [CardLike("A"), CardLike("B")]
    card_list = HorizontalCardList.__new__(HorizontalCardList)
    card_list.client = client
    card_list.cards = cards
    card_list.escapable = True
    card_list.current_col = 0
    card_list.return_value = None
    card_list.set_return_value = MagicMock(side_effect=lambda value: setattr(card_list, "return_value", value))
    card_list.Bind = MagicMock()
    card_list.populate()
    assert card_list_ui.HorizontalMenu.append_item.call_count == 2

    card_list.finalize(1)
    assert card_list.return_value == 1
    stack.pop_ui.assert_called()

    event = MagicMock()
    event.GetKeyCode.return_value = 32
    card_list.on_key_down(event)
    from ui.card_list_ui import utils
    utils.output.assert_called()

    event.GetKeyCode.return_value = 27
    card_list.escapable = False
    card_list.on_key_down(event)
    assert any("Not allowed" in str(c) for c in utils.output.call_args_list)
    card_list.escapable = True
    card_list.on_key_down(event)
    assert card_list.return_value == -1

    event.GetKeyCode.return_value = 99
    client.get_duel_field.return_value.preemtive_key_handler = MagicMock(return_value=True)
    card_list.on_key_down(event)
    client.get_duel_field.return_value.preemtive_key_handler.assert_called()


def test_rps_rematch_and_packet_handlers(mocker):
    from game.edo import structs
    from ui import rematch_ui, rock_paper_scissors_ui

    mocker.patch("ui.rock_paper_scissors_ui.HorizontalMenu", FakeMenu)
    mocker.patch("ui.rock_paper_scissors_ui.StatusMessageWithoutTimelimit", FakeStatus)
    mocker.patch("ui.rematch_ui.HorizontalMenu", FakeMenu)
    mocker.patch("ui.rematch_ui.StatusMessageWithoutTimelimit", FakeStatus)
    mocker.patch("ui.rock_paper_scissors_ui.utils.output")
    client = MagicMock()

    menu = rock_paper_scissors_ui.show_rock_paper_scissors_ui.__wrapped__(client)
    assert [item[0] for item in menu.items] == ["Rock", "Paper", "Scissors"]
    status = rock_paper_scissors_ui.send_rps_choice.__wrapped__(client, 2)
    assert isinstance(status, FakeStatus)
    client.send.assert_called()
    mocker.patch("ui.rock_paper_scissors_ui.show_rock_paper_scissors_ui", return_value=FakeMenu("RPS"))
    assert rock_paper_scissors_ui.handle_rps_result.__wrapped__(client, 1, 1)
    assert rock_paper_scissors_ui.handle_rps_result.__wrapped__(client, 2, 1) is None
    assert isinstance(rock_paper_scissors_ui.handle_rps_result.__wrapped__(client, 1, 2), FakeStatus)
    order = rock_paper_scissors_ui.show_choose_order_ui.__wrapped__(client)
    assert [item[0] for item in order.items] == ["First", "Second"]
    rock_paper_scissors_ui.send_order_choice(client, 1)
    rock_paper_scissors_ui.handle_rock_paper_scissors(client, b"", 0)
    packet = structs.StocRPSResult()
    packet.result0 = 2
    packet.result1 = 1
    mocker.patch("ui.rock_paper_scissors_ui.handle_rps_result")
    rock_paper_scissors_ui.handle_rock_paper_scissors_result(client, bytes(packet), len(bytes(packet)))
    mocker.patch("ui.rock_paper_scissors_ui.show_choose_order_ui", return_value=FakeMenu("Order"))
    rock_paper_scissors_ui.handle_choose_order(client, b"", 0)

    menu = rematch_ui.show_rematch_ui.__wrapped__(client)
    assert [item[0] for item in menu.items] == ["Yes", "No"]
    assert isinstance(rematch_ui._rematch_yes.__wrapped__(client), FakeStatus)
    client.send.assert_called_with(structs.ClientIdType.REMATCH, struct.pack("B", 1))
    assert isinstance(rematch_ui._rematch_no.__wrapped__(client), FakeStatus)
    client.send.assert_called_with(structs.ClientIdType.REMATCH, struct.pack("B", 0))
    mocker.patch("ui.rematch_ui.show_rematch_ui", return_value=FakeMenu("Rematch"))
    assert rematch_ui.handle_rematch(client, b"", 0)
    assert rematch_ui.handle_rematch_wait(client, b"", 0) is None
