"""Browsable history of a duel: what happened, and what the player did.

The spoken replay (F9, H) reads the last few announcements aloud and then they
are gone again. That answers "what did I just miss?" but not "how did we get
here?", which is the question when the duel does something unexpected. This
screen keeps the whole duel in one list the player can walk through at their own
pace, with their own choices interleaved so a surprising board state can be
traced back to the move that caused it.
"""

import logging

import wx

from core import speech
from core import utils
from core.i18n import _
from ui.base_ui import VerticalMenu

logger = logging.getLogger(__name__)


def format_entry(entry, started_at):
    """One history line: when it happened, who caused it, and what it was."""
    elapsed = max(0, int(entry.at - started_at))
    stamp = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
    if entry.kind == speech.Kind.ACTION:
        return _("{time} You: {text}").format(time=stamp, text=entry.text)
    return _("{time} {text}").format(time=stamp, text=entry.text)


def history_lines():
    """The whole history, oldest first, as readable lines."""
    entries = speech.MESSAGE_LOG.entries()
    if not entries:
        return []
    started_at = entries[0].at
    return [format_entry(entry, started_at) for entry in entries]


def copy_history_to_clipboard(lines):
    """Put the history on the clipboard, so it can go into a bug report."""
    if not lines:
        return False
    try:
        clipboard = wx.TheClipboard
        if not clipboard.Open():
            return False
        try:
            clipboard.SetData(wx.TextDataObject("\n".join(lines)))
            clipboard.Flush()
        finally:
            clipboard.Close()
    except Exception:
        logger.exception("Could not copy the duel history to the clipboard")
        return False
    return True


def _copy(lines):
    if copy_history_to_clipboard(lines):
        utils.output(_("Duel history copied to the clipboard."), priority=speech.Priority.CRITICAL)
    else:
        utils.output(_("Could not copy the duel history."), priority=speech.Priority.CRITICAL)


@utils.ui_function
def show_duel_history(client=None):
    lines = history_lines()
    menu = VerticalMenu(_("Duel History"))
    if not lines:
        menu.append_item(_("Nothing has happened yet."))
    else:
        menu.append_item(
            _("{count} entries, oldest first.").format(count=len(lines))
        )
        for line in lines:
            menu.append_item(line)
        menu.append_item(_("Copy history to clipboard"), function=lambda: _copy(lines))
    menu.append_cancel_item(_("Close"), function=lambda: utils.get_ui_stack().pop_ui())
    menu.set_help_text(
        _("Arrow keys to walk through the duel, oldest first. Lines starting with You are your own choices. Escape or Close returns to the duel.")
    )
    return menu
