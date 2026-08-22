from unittest.mock import MagicMock

import pytest
import wx


class FakeCard:
    def __init__(self, name="Card"):
        self.name = name

    def get_name(self):
        return self.name

    def __str__(self):
        return f"Details for {self.name}"


class FakeKeyEvent:
    def __init__(self, key):
        self.key = key

    def GetKeyCode(self):
        return self.key


def _card_list(mocker, escapable=True):
    from ui import card_list_ui

    mocker.patch("ui.card_list_ui.Card", FakeCard)
    mocker.patch("ui.card_list_ui.HorizontalMenu.__init__", return_value=None)
    mocker.patch("ui.card_list_ui.HorizontalMenu.append_item")
    mocker.patch("ui.card_list_ui.HorizontalMenu.on_key_down")
    mocker.patch("ui.card_list_ui.HorizontalCardList.Bind")
    mocker.patch("ui.card_list_ui.utils.output")
    stack = MagicMock()
    mocker.patch("ui.card_list_ui.utils.get_ui_stack", return_value=stack)

    field = MagicMock()
    field.resolve_labels_for_card.side_effect = lambda card: "Label"
    field.get_card_accessibility_details.side_effect = lambda card: ["detail"] if card.name == "A" else []
    field.preemtive_key_handler = None
    client = MagicMock()
    client.get_duel_field.return_value = field

    cards = [FakeCard("A"), FakeCard("B")]
    card_list = card_list_ui.HorizontalCardList(client, "Cards", cards, escapable=escapable)
    card_list.current_col = 0
    card_list.return_value = None
    card_list.set_return_value = MagicMock(side_effect=lambda value: setattr(card_list, "return_value", value))
    return card_list_ui, card_list, client, stack


def test_horizontal_card_list_init_validation_and_population(mocker):
    card_list_ui, card_list, _client, _stack = _card_list(mocker)

    assert card_list.cards[0].name == "A"
    assert card_list_ui.HorizontalMenu.append_item.call_count == 2
    first_label = card_list_ui.HorizontalMenu.append_item.call_args_list[0].args[0]
    second_label = card_list_ui.HorizontalMenu.append_item.call_args_list[1].args[0]
    assert "A" in first_label and "detail" in first_label
    assert "B" in second_label

    with pytest.raises(ValueError):
        card_list_ui.HorizontalCardList(MagicMock(), "Bad", [object()])


def test_horizontal_card_list_select_finalize_and_keys(mocker):
    card_list_ui, card_list, client, stack = _card_list(mocker)

    mocker.patch("ui.card_list_ui.wx.Yield", side_effect=lambda: setattr(card_list, "return_value", 1))
    assert card_list.select_card() == 1
    stack.push_ui.assert_called_with(card_list)

    card_list.finalize(0)
    assert card_list.return_value == 0
    stack.pop_ui.assert_called()

    card_list.current_col = 1
    card_list.on_key_down(FakeKeyEvent(wx.WXK_SPACE))
    assert "Details for B" in card_list_ui.utils.output.call_args.args[0]

    card_list.escapable = False
    card_list.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))
    assert card_list_ui.utils.output.call_args.args[0] == "Not allowed"

    card_list.escapable = True
    card_list.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))
    assert card_list.return_value == -1

    client.get_duel_field.return_value.preemtive_key_handler = MagicMock(return_value=True)
    card_list.on_key_down(FakeKeyEvent(ord("X")))
    client.get_duel_field.return_value.preemtive_key_handler.assert_called()

    client.get_duel_field.return_value.preemtive_key_handler = MagicMock(return_value=False)
    card_list.on_key_down(FakeKeyEvent(ord("Y")))
    card_list_ui.HorizontalMenu.on_key_down.assert_called()
