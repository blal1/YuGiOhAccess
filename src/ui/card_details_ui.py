"""The one place a card's full text is presented.

Before this module there were three: the duel field read a card with N/D/T/L/A,
the card search had its own line-by-line reader, and the deck editor just dumped
``str(card)`` into the speech stream. Same card, three experiences.

Two accessibility rules shape the design:

* Never take a key the platform already handles better. A read-only
  ``wx.TextCtrl`` gives a screen reader caret navigation by character, word and
  line, plus selection and copy, for free. The old reader bound Up, Down, Home,
  End, Space and Enter on that control and replaced all of it with a worse
  home-made line walker. Here the text control is left completely alone.
* Give the segments their own native widget instead. The list box beside the
  text does the line-by-line reading, and a list box already announces its
  selection on arrow keys without a single key binding.

Long effect text is split into sentences so that "line 3 of 9" means something.
Splitting only on newlines, as before, gave one 300 character "line".
"""

import logging
import re

import wx

from core import utils
from core.i18n import _
from game.card.card import Card
from ui.base_ui import VerticalMenu

logger = logging.getLogger(__name__)

# A sentence ends at ., !, ?, or their full width equivalents, followed by
# whitespace. Kept deliberately simple: this is for reading aloud, not parsing.
SENTENCE_END = re.compile(r"(?<=[.!?。！？])\s+")

# Sentences longer than this are split again on clause boundaries, so that a
# single segment stays within a comfortable listening length.
LONG_SEGMENT = 200
CLAUSE_END = re.compile(r"(?<=[;:；：])\s+")


def _as_card(card_or_code):
    """Accept either a Card or a card code.

    Duck typed rather than isinstance based so that callers, and tests that
    replace Card, keep working.
    """
    if hasattr(card_or_code, "get_name"):
        return card_or_code
    return Card(card_or_code)


def card_detail_text(card_or_code):
    """Full readable text for a card, accepting either a Card or a card code."""
    return str(_as_card(card_or_code))


def split_card_detail_lines(detail_text):
    """Break card text into segments a listener can follow one at a time."""
    segments = []
    for raw_line in detail_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        for sentence in SENTENCE_END.split(line):
            sentence = sentence.strip()
            if not sentence:
                continue
            if len(sentence) <= LONG_SEGMENT:
                segments.append(sentence)
                continue
            for clause in CLAUSE_END.split(sentence):
                clause = clause.strip()
                if clause:
                    segments.append(clause)
    return segments or [_("No details.")]


class CardDetailReaderUI(wx.Panel):
    """Read one card in full: segment by segment, or all at once.

    Navigation lives in the list box, which announces each segment natively on
    arrow keys. The text control below holds the same text unmodified so the
    screen reader's own caret navigation and copy still work.
    """

    def __init__(self, code, name=None, detail_text=None):
        super().__init__(wx.GetTopLevelWindows()[0], style=wx.WANTS_CHARS, name=_("Card details"))
        self.code = code
        self.card_name = name or ""
        self.detail_text = detail_text if detail_text is not None else card_detail_text(code)
        self.lines = split_card_detail_lines(self.detail_text)
        self.current_line = 0

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.StaticText(self, label=_("{name} details").format(name=self.card_name or _("Card")))
        self.header.SetName(_("Card detail header"))
        sizer.Add(self.header, 0, wx.EXPAND | wx.ALL, 6)

        self.line_label = wx.StaticText(self, label="")
        self.line_label.SetName(_("Current detail line"))
        sizer.Add(self.line_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        # Arrow keys on a list box are handled by the platform and announced by
        # the screen reader, so segment navigation needs no key bindings at all.
        self.line_list = wx.ListBox(self, choices=list(self.lines), style=wx.WANTS_CHARS)
        self.line_list.SetName(_("Card text, line by line"))
        self.line_list.SetToolTip(_("Use up and down to read one line at a time."))
        sizer.Add(self.line_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.details = wx.TextCtrl(self, value=self.detail_text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.WANTS_CHARS)
        self.details.SetName(_("Full card text"))
        self.details.SetToolTip(_("The complete card text. Read it with your screen reader as usual, or copy it."))
        sizer.Add(self.details, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.previous_line_button = wx.Button(self, label=_("Previous line"))
        self.read_line_button = wx.Button(self, label=_("Read line"))
        self.next_line_button = wx.Button(self, label=_("Next line"))
        self.read_all_button = wx.Button(self, label=_("Read all"))
        self.copy_button = wx.Button(self, label=_("Copy card text"))
        self.back_button = wx.Button(self, label=_("Back"))
        for button in (
            self.previous_line_button, self.read_line_button, self.next_line_button,
            self.read_all_button, self.copy_button, self.back_button,
        ):
            buttons.Add(button, 0, wx.ALL, 4)
        sizer.Add(buttons, 0, wx.ALIGN_CENTER)
        self.SetSizer(sizer)

        self.previous_line_button.Bind(wx.EVT_BUTTON, lambda event: self.move_line(-1))
        self.read_line_button.Bind(wx.EVT_BUTTON, lambda event: self.read_current_line())
        self.next_line_button.Bind(wx.EVT_BUTTON, lambda event: self.move_line(1))
        self.read_all_button.Bind(wx.EVT_BUTTON, lambda event: self.read_all())
        self.copy_button.Bind(wx.EVT_BUTTON, lambda event: self.copy_to_clipboard())
        self.back_button.Bind(wx.EVT_BUTTON, lambda event: self.go_back())
        self.line_list.Bind(wx.EVT_LISTBOX, self.on_line_selected)
        # Deliberately not bound on self.details: that control stays native.
        self.line_list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.line_list.SetSelection(0)
        self.update_line(announce=True)
        self.line_list.SetFocus()

    def on_line_selected(self, event):
        selection = self.line_list.GetSelection()
        if selection >= 0:
            self.current_line = selection
            self.update_line(announce=True)

    def update_line(self, announce=False):
        line = self.lines[self.current_line] if self.lines else _("No details.")
        label = _("{position} of {count}: {line}").format(
            position=self.current_line + 1,
            count=len(self.lines),
            line=line,
        )
        self.line_label.SetLabel(label)
        if announce:
            utils.output(label)

    def move_line(self, delta):
        if not self.lines:
            return
        self.current_line = (self.current_line + delta) % len(self.lines)
        line_list = getattr(self, "line_list", None)
        if line_list is not None and line_list.GetCount():
            line_list.SetSelection(self.current_line)
        self.update_line(announce=True)

    def read_current_line(self):
        self.update_line(announce=True)

    def read_all(self):
        utils.output(self.detail_text)

    def copy_to_clipboard(self):
        if not wx.TheClipboard.Open():
            utils.output(_("Could not use the clipboard."))
            return
        try:
            wx.TheClipboard.SetData(wx.TextDataObject(self.detail_text))
        finally:
            wx.TheClipboard.Close()
        utils.output(_("Card text copied to clipboard."))

    def go_back(self):
        utils.get_ui_stack().pop_ui()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_SPACE):
            self.read_all()
            return
        if key == wx.WXK_ESCAPE:
            self.go_back()
            return
        if key == wx.WXK_F1:
            utils.output(
                _(
                    "Card details. Up and down read the card one line at a time. "
                    "Tab reaches the full text, where your screen reader reads and copies as usual. "
                    "Space or Enter reads everything, and Escape goes back."
                )
            )
            return
        # Everything else, including arrow keys inside the text, belongs to the
        # platform and the screen reader.
        event.Skip()


def show_card_details(card_or_code, name=None):
    """Push the shared reader for a card. Works in and out of a duel."""
    card = _as_card(card_or_code)
    detail_text = str(card)
    reader = CardDetailReaderUI(card.code, name or card.get_name(), detail_text=detail_text)
    utils.get_ui_stack().push_ui(reader)
    return reader


class CardChoiceMenu(VerticalMenu):
    """A vertical menu of cards where Space reads the card before you commit.

    The deck editor used to list bare card names, so the only way to find out
    what a card did was to add it and then go looking for it in the deck list.
    Any list of cards offered as a choice should use this instead.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.codes_by_row = {}

    def append_card(self, code, label, function=None):
        item = self.append_item(str(label), function)
        self.codes_by_row[self.rows - 1] = code
        return item

    def current_code(self):
        return self.codes_by_row.get(self.current_row)

    def read_current_card(self):
        code = self.current_code()
        if code is None:
            utils.output(_("No card on this line."))
            return None
        return show_card_details(code)

    def on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_SPACE:
            self.read_current_card()
            return
        super().on_key_down(event)
