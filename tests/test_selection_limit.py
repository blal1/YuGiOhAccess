"""Checkbox selections must not let the player build an answer the duel refuses.

Ticking a second card when only one may be chosen produced an invalid response,
which the core rejected and re-prompted. The limit is now enforced while
choosing: the oldest tick makes way for the newest.
"""

import pytest

from ui.selection_limit import SelectionLimiter


class FakeCheckbox:
    def __init__(self, label="", checked=False):
        self.label = label
        self.checked = checked
        self.bindings = []

    def IsChecked(self):
        return self.checked

    def SetValue(self, value):
        self.checked = bool(value)

    def GetLabel(self):
        return self.label

    def Bind(self, event, handler):
        self.bindings.append((event, handler))


def _limiter(maximum, count=3, spoken=None):
    limiter = SelectionLimiter(maximum, announce=spoken.append if spoken is not None else None)
    boxes = [FakeCheckbox(f"Card {i}") for i in range(count)]
    for box in boxes:
        limiter.add(box)
    return limiter, boxes


def _tick(limiter, box):
    box.SetValue(True)
    limiter.on_toggle(box)


def test_a_second_choice_replaces_the_first_when_only_one_is_allowed():
    limiter, boxes = _limiter(1)

    _tick(limiter, boxes[0])
    _tick(limiter, boxes[1])

    assert boxes[0].IsChecked() is False
    assert boxes[1].IsChecked() is True


def test_the_oldest_choice_is_the_one_that_makes_way():
    limiter, boxes = _limiter(2)

    _tick(limiter, boxes[0])
    _tick(limiter, boxes[1])
    _tick(limiter, boxes[2])

    assert [box.IsChecked() for box in boxes] == [False, True, True]


def test_choices_below_the_limit_are_all_kept():
    limiter, boxes = _limiter(3)

    for box in boxes:
        _tick(limiter, box)

    assert all(box.IsChecked() for box in boxes)


def test_unticking_frees_a_slot():
    limiter, boxes = _limiter(1)

    _tick(limiter, boxes[0])
    boxes[0].SetValue(False)
    limiter.on_toggle(boxes[0])
    _tick(limiter, boxes[1])

    assert boxes[1].IsChecked() is True
    assert limiter.selected() == [boxes[1]]


def test_reticking_the_same_box_does_not_evict_it():
    limiter, boxes = _limiter(1)

    _tick(limiter, boxes[0])
    _tick(limiter, boxes[0])

    assert boxes[0].IsChecked() is True


@pytest.mark.parametrize("maximum", [0, -1, None])
def test_no_limit_means_no_eviction(maximum):
    limiter, boxes = _limiter(maximum)

    for box in boxes:
        _tick(limiter, box)

    assert all(box.IsChecked() for box in boxes)


def test_the_player_is_told_which_card_was_unticked():
    spoken = []
    limiter, boxes = _limiter(1, spoken=spoken)

    _tick(limiter, boxes[0])
    _tick(limiter, boxes[1])

    assert len(spoken) == 1
    assert "Card 0" in spoken[0]


def test_nothing_is_announced_while_below_the_limit():
    spoken = []
    limiter, boxes = _limiter(2, spoken=spoken)

    _tick(limiter, boxes[0])
    _tick(limiter, boxes[1])

    assert spoken == []


def test_it_listens_to_each_box_it_is_given():
    limiter, boxes = _limiter(1)

    assert all(box.bindings for box in boxes)


def test_a_box_that_cannot_be_bound_is_still_limited():
    class Unbindable(FakeCheckbox):
        def Bind(self, event, handler):
            raise RuntimeError("no event loop")

    limiter = SelectionLimiter(1)
    first, second = Unbindable("A"), Unbindable("B")
    limiter.add(first)
    limiter.add(second)

    _tick(limiter, first)
    _tick(limiter, second)

    assert first.IsChecked() is False


# ----------------------------------------------------- wired into the menus --

def test_select_card_limits_the_menu_to_what_the_duel_allows(mocker):
    from tests.test_duel_messages_simple_more import NamedCard, _client
    from tests.test_ui_flows_more import FakeMenu
    from ui.duel_messages import select_card

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.select_card.VerticalMenu", FakeMenu)
    location = mocker.MagicMock()
    location.to_human_readable.return_value = "your hand"
    mocker.patch(
        "ui.duel_messages.select_card.LocationConversion.from_card_location",
        return_value=location,
    )
    limiter = mocker.patch("ui.duel_messages.select_card.SelectionLimiter")

    select_card.select_card(client, 0, False, 1, 1, [NamedCard("A"), NamedCard("B")])

    limiter.assert_called_once_with(1)
    assert limiter.return_value.add.call_count == 2


def test_too_few_cards_is_refused_instead_of_sent(mocker):
    from tests.test_duel_messages_simple_more import NamedCard, _client
    from ui.duel_messages import select_card

    client, _stack = _client(mocker)
    output = mocker.patch("ui.duel_messages.select_card.utils.output")
    menu = mocker.MagicMock()
    menu.cells = []

    select_card.finish_card_selection(client, menu, [NamedCard("A")], 1, 1, False)

    client.send.assert_not_called()
    assert "at least" in str(output.call_args)


def test_too_many_cards_is_refused_instead_of_sent(mocker):
    from tests.test_duel_messages_simple_more import NamedCard, _client
    from ui.duel_messages import select_card

    client, _stack = _client(mocker)
    output = mocker.patch("ui.duel_messages.select_card.utils.output")
    mocker.patch("ui.duel_messages.select_card.wx.CheckBox", FakeCheckbox)
    menu = mocker.MagicMock()
    menu.cells = [[FakeCheckbox(checked=True)], [FakeCheckbox(checked=True)]]

    select_card.finish_card_selection(client, menu, [NamedCard("A")], 1, 1, False)

    client.send.assert_not_called()
    assert "at most" in str(output.call_args)
