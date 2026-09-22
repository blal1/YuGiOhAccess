"""The screens a blind player leans on hardest, and the least exercised.

The duel history, the selection limiter and the card reader are the parts of
the client that exist purely for accessibility, and they were the parts with
the least test coverage: the clipboard paths, the announcements when a choice
is released, and every fallback in the card reader were all unrun.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import wx


# ------------------------------------------------------------- duel history --

def _entries():
    from core import speech

    return [
        speech.LogEntry(10.0, "Duel starting", speech.Priority.INFO, True, speech.Kind.MESSAGE),
        speech.LogEntry(75.0, "Summon Blue-Eyes", speech.Priority.INFO, False, speech.Kind.ACTION),
        speech.LogEntry(140.0, "You win", speech.Priority.CRITICAL, True, speech.Kind.MESSAGE),
    ]


def test_history_lines_are_stamped_from_the_start_of_the_duel(mocker):
    from core import speech
    from ui import duel_history_ui

    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=_entries())

    lines = duel_history_ui.history_lines()

    assert lines[0].startswith("00:00")
    assert lines[1].startswith("01:05 You: Summon Blue-Eyes")
    assert lines[2].startswith("02:10")


def test_an_empty_history_has_no_lines(mocker):
    from core import speech
    from ui import duel_history_ui

    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=[])

    assert duel_history_ui.history_lines() == []


def test_copying_the_history_puts_it_on_the_clipboard(mocker):
    from ui import duel_history_ui

    clipboard = MagicMock()
    clipboard.Open.return_value = True
    mocker.patch("ui.duel_history_ui.wx.TheClipboard", clipboard)
    mocker.patch("ui.duel_history_ui.wx.TextDataObject", side_effect=lambda text: text)

    assert duel_history_ui.copy_history_to_clipboard(["one", "two"]) is True
    clipboard.SetData.assert_called_once_with("one\ntwo")
    clipboard.Close.assert_called_once()


def test_copying_nothing_is_not_reported_as_success():
    from ui import duel_history_ui

    assert duel_history_ui.copy_history_to_clipboard([]) is False


def test_a_clipboard_that_will_not_open_is_reported(mocker):
    from ui import duel_history_ui

    clipboard = MagicMock()
    clipboard.Open.return_value = False
    mocker.patch("ui.duel_history_ui.wx.TheClipboard", clipboard)

    assert duel_history_ui.copy_history_to_clipboard(["one"]) is False


def test_a_clipboard_that_throws_does_not_take_the_duel_down(mocker):
    from ui import duel_history_ui

    clipboard = MagicMock()
    clipboard.Open.side_effect = RuntimeError("no clipboard here")
    mocker.patch("ui.duel_history_ui.wx.TheClipboard", clipboard)

    assert duel_history_ui.copy_history_to_clipboard(["one"]) is False


@pytest.mark.parametrize("succeeded,expected", [(True, "copied"), (False, "Could not copy")])
def test_the_player_is_told_whether_the_copy_worked(mocker, succeeded, expected):
    from ui import duel_history_ui

    mocker.patch("ui.duel_history_ui.copy_history_to_clipboard", return_value=succeeded)
    output = mocker.patch("ui.duel_history_ui.utils.output")

    duel_history_ui._copy(["one"])

    assert expected in output.call_args.args[0]


def test_the_history_screen_lists_the_duel(mocker):
    from core import speech
    from tests.test_ui_flows_more import FakeMenu
    from ui import duel_history_ui

    mocker.patch("ui.duel_history_ui.VerticalMenu", FakeMenu)
    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=_entries())

    menu = duel_history_ui.show_duel_history.__wrapped__(MagicMock())

    labels = [str(item[0]) for item in menu.items]
    assert any("3 entries" in label for label in labels)
    assert any("Duel starting" in label for label in labels)


def test_the_history_screen_says_when_nothing_has_happened(mocker):
    from core import speech
    from tests.test_ui_flows_more import FakeMenu
    from ui import duel_history_ui

    mocker.patch("ui.duel_history_ui.VerticalMenu", FakeMenu)
    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=[])

    menu = duel_history_ui.show_duel_history.__wrapped__(MagicMock())

    assert any("Nothing has happened yet" in str(item[0]) for item in menu.items)


# ---------------------------------------------------------- selection limit --

class FakeCheckBox:
    """Enough of a wx.CheckBox for the limiter to work with."""

    def __init__(self, label="a card", checked=False):
        self.label = label
        self.checked = checked
        self.bound = None

    def IsChecked(self):
        return self.checked

    def SetValue(self, value):
        self.checked = value

    def GetLabel(self):
        return self.label

    def Bind(self, event, handler):
        self.bound = handler


def test_ticking_past_the_limit_releases_the_oldest_choice():
    from ui.selection_limit import SelectionLimiter

    said = []
    limiter = SelectionLimiter(2, announce=said.append)
    boxes = [FakeCheckBox(f"card {i}") for i in range(3)]
    for box in boxes:
        limiter.add(box)

    for box in boxes:
        box.checked = True
        limiter.on_toggle(box)

    assert [box.checked for box in boxes] == [False, True, True]
    assert "card 0" in said[0]


def test_unticking_removes_a_choice_from_the_group():
    from ui.selection_limit import SelectionLimiter

    limiter = SelectionLimiter(2, announce=lambda text: None)
    box = FakeCheckBox()
    limiter.add(box)
    box.checked = True
    limiter.on_toggle(box)
    assert limiter.selected() == [box]

    box.checked = False
    limiter.on_toggle(box)
    assert limiter.selected() == []


def test_a_limit_of_zero_means_no_limit():
    from ui.selection_limit import SelectionLimiter

    limiter = SelectionLimiter(0, announce=lambda text: None)
    boxes = [FakeCheckBox() for _ in range(4)]
    for box in boxes:
        limiter.add(box)
        box.checked = True
        limiter.on_toggle(box)

    assert all(box.checked for box in boxes)


def test_a_checkbox_already_ticked_when_added_counts():
    from ui.selection_limit import SelectionLimiter

    limiter = SelectionLimiter(1, announce=lambda text: None)
    limiter.add(FakeCheckBox(checked=True))

    assert len(limiter.selected()) == 1


def test_a_checkbox_that_cannot_be_bound_is_still_limited(mocker):
    """Outside a running app Bind throws; the limit still has to hold."""
    from ui.selection_limit import SelectionLimiter

    class Unbindable(FakeCheckBox):
        def Bind(self, event, handler):
            raise RuntimeError("no app")

    limiter = SelectionLimiter(1, announce=lambda text: None)
    first, second = Unbindable("one"), Unbindable("two")
    limiter.add(first)
    limiter.add(second)
    for box in (first, second):
        box.checked = True
        limiter.on_toggle(box)

    assert (first.checked, second.checked) == (False, True)


def test_a_checkbox_that_will_not_untick_is_logged_not_raised():
    from ui.selection_limit import SelectionLimiter

    class Stubborn(FakeCheckBox):
        def SetValue(self, value):
            raise RuntimeError("gone")

    limiter = SelectionLimiter(1, announce=lambda text: None)
    boxes = [Stubborn("one"), Stubborn("two")]
    for box in boxes:
        limiter.add(box)
        box.checked = True
        limiter.on_toggle(box)  # must not raise


def test_limit_checkboxes_labels_each_one():
    from ui.selection_limit import limit_checkboxes

    said = []
    boxes = [FakeCheckBox() for _ in range(3)]
    limiter = limit_checkboxes(boxes, 1, labels=["first", "second", "third"], announce=said.append)
    for box in boxes:
        box.checked = True
        limiter.on_toggle(box)

    assert "first" in said[0]


def test_the_default_announcement_reaches_the_screen_reader(mocker):
    from core import speech
    from ui import selection_limit

    output = mocker.patch("ui.selection_limit.utils.output")

    selection_limit._announce("released")

    output.assert_called_once_with("released", priority=speech.Priority.CRITICAL)


@pytest.mark.parametrize("box,expected", [
    (SimpleNamespace(GetValue=lambda: True), True),
    (SimpleNamespace(IsChecked=lambda: True), True),
    (SimpleNamespace(), False),
])
def test_a_checkbox_is_read_however_it_reports_itself(box, expected):
    from ui.selection_limit import _is_checked

    assert _is_checked(box) is expected


def test_a_checkbox_that_throws_when_read_counts_as_unticked():
    from ui.selection_limit import _is_checked

    def explode():
        raise RuntimeError("gone")

    assert _is_checked(SimpleNamespace(IsChecked=explode)) is False


def test_a_label_falls_back_through_what_the_control_offers():
    from ui.selection_limit import _label_of

    assert _label_of(SimpleNamespace(GetLabel=lambda: "named")) == "named"
    assert _label_of(SimpleNamespace(GetName=lambda: "by name")) == "by name"
    assert _label_of(SimpleNamespace(), fallback="nothing") == "nothing"


# ------------------------------------------------------------- card reader --

def test_long_card_text_is_split_into_sentences():
    from ui.card_details_ui import split_card_detail_lines

    lines = split_card_detail_lines("First sentence. Second one! A third?\n\nAnd a new line.")

    assert lines == ["First sentence.", "Second one!", "A third?", "And a new line."]


def test_a_very_long_sentence_is_split_again_at_clauses():
    from ui.card_details_ui import LONG_SEGMENT, split_card_detail_lines

    first = "a" * (LONG_SEGMENT - 10)
    second = "b" * 40
    lines = split_card_detail_lines(f"{first}; {second}")

    assert len(lines) == 2


def test_a_card_with_no_text_still_reads_as_something():
    from ui.card_details_ui import split_card_detail_lines

    assert split_card_detail_lines("   \n  ") == ["No details."]


def test_a_card_is_accepted_as_an_object_or_a_code(mocker):
    from ui import card_details_ui

    card = SimpleNamespace(get_name=lambda: "Blue-Eyes")
    assert card_details_ui._as_card(card) is card

    made = mocker.patch("ui.card_details_ui.Card", return_value=card)
    assert card_details_ui._as_card(1234) is card
    made.assert_called_once_with(1234)


def test_the_card_choice_menu_tracks_what_is_under_the_cursor(mocker):
    from ui.card_details_ui import CardChoiceMenu

    menu = CardChoiceMenu.__new__(CardChoiceMenu)
    menu.codes_by_row = {}
    menu.rows = 0
    menu.current_row = 0

    def append_item(label, function=None):
        menu.rows += 1
        return label

    menu.append_item = append_item
    menu.append_card(111, "Blue-Eyes")
    menu.append_card(222, "Dark Magician")

    menu.current_row = 0
    assert menu.current_code() == 111
    menu.current_row = 1
    assert menu.current_code() == 222
    menu.current_row = 9
    assert menu.current_code() is None


def test_reading_a_line_with_no_card_says_so(mocker):
    from ui.card_details_ui import CardChoiceMenu

    output = mocker.patch("ui.card_details_ui.utils.output")
    menu = CardChoiceMenu.__new__(CardChoiceMenu)
    menu.codes_by_row = {}
    menu.current_row = 0

    assert menu.read_current_card() is None
    assert "No card on this line" in output.call_args.args[0]


def test_space_on_a_card_list_reads_the_card(mocker):
    from ui.card_details_ui import CardChoiceMenu

    shown = mocker.patch("ui.card_details_ui.show_card_details")
    menu = CardChoiceMenu.__new__(CardChoiceMenu)
    menu.codes_by_row = {0: 555}
    menu.current_row = 0

    menu.on_key_down(SimpleNamespace(GetKeyCode=lambda: wx.WXK_SPACE))

    shown.assert_called_once_with(555)
