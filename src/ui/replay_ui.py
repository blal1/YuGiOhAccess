"""Saved duels: recording them, and reading them back.

Two different things live here, and keeping them apart matters.

* A **duel log** is this client's own record of a duel in words: every
  announcement and every choice, in order, saved when the duel ends. It is
  written for every duel, including offline ones, and the viewer reads it
  back. This is the thing a screen reader user can actually review.
* A **replay file** is a server's own record of the duel, saved verbatim.
  An online server sends the core's format, which is kept as a .yrp and opens
  in EDOPro. The bundled server cannot produce one of those, so it sends its
  own container instead, kept as a .ygoarep. Each is named for what it holds:
  a file EDOPro cannot open should not be called a .yrp.

Before this, neither worked: offline duels recorded nothing, and the viewer
could only report a file's size and copy its bytes out as hex.
"""

from datetime import datetime
from pathlib import Path

import wx

from core import speech, utils, variables
from core.i18n import _
from game import duel_log
from server import replay as server_replay
from ui.base_ui import VerticalMenu


def get_replay_dir():
    return Path(variables.APP_DATA_DIR) / "replays"


# ------------------------------------------------------- recording a duel ---

def save_replay_packet(client, packet_data, new=False):
    """Append replay bytes a server sent us, as they arrived.

    These are the core's own replay format; we do not parse them, we keep
    them so they can be opened in EDOPro.
    """
    replay_dir = get_replay_dir()
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_file = getattr(client.memory, "replay_file", None)
    if new or not replay_file:
        room_id = getattr(client, "room_id", None) or "unknown"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Named by what it holds. The bundled server cannot produce a file
        # EDOPro would open, so calling its records .yrp would leave the
        # player with files no program can read.
        suffix = ".ygoarep" if server_replay.is_ours(bytes(packet_data)) else ".yrp"
        replay_file = replay_dir / f"duel_{timestamp}_{room_id}{suffix}"
        client.memory.replay_file = replay_file
        replay_file.write_bytes(b"")
    with open(replay_file, "ab") as replay:
        replay.write(bytes(packet_data))
    return replay_file


def record_duel_log(client=None):
    """Write what was said during this duel, so it can be read back.

    Called when the duel ends. The history is in memory either way; saving it
    is the difference between a replay viewer that lists files and one that
    can tell you what happened.
    """
    entries = speech.MESSAGE_LOG.entries()
    if not entries:
        return None
    room_id = getattr(client, "room_id", None) if client is not None else None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = get_replay_dir() / f"duel_{timestamp}_{room_id or 'local'}{duel_log.SUFFIX}"
    try:
        return duel_log.write(path, entries, room_id=room_id)
    except OSError:
        # A duel that cannot be saved is not a duel that should fail.
        utils.output(_("The duel log could not be saved."))
        return None


def finish_replay_recording(client=None):
    """Close off the recording for a duel that has just ended."""
    saved = record_duel_log(client)
    if client is not None and hasattr(client, "memory"):
        client.memory.replay_file = None
    if saved is not None:
        utils.output(_("Duel saved for review as {name}").format(name=saved.name))
    return saved


# ---------------------------------------------------------- reading it back --

def _saved_duels():
    """Every duel log on disk, newest first."""
    replay_dir = get_replay_dir()
    replay_dir.mkdir(parents=True, exist_ok=True)
    return sorted(
        (path for path in replay_dir.glob(f"*{duel_log.SUFFIX}") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _replay_files():
    """Core replay files a server sent us, newest first."""
    replay_dir = get_replay_dir()
    replay_dir.mkdir(parents=True, exist_ok=True)
    return sorted(
        (path for path in replay_dir.iterdir()
         if path.is_file() and path.suffix in (".yrp", ".ygoarep")),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


@utils.ui_function
def replay_viewer_menu(return_to=None):
    if not return_to:
        from ui.main_ui import main_menu_view
        return_to = main_menu_view
    menu = VerticalMenu(_("Replay Viewer"))
    menu.set_help_text(_(
        "Duels you have played, most recent first. Enter opens one and reads it "
        "back a line at a time."
    ))

    duels = _saved_duels()
    if not duels:
        menu.append_item(_("No saved duels yet."), None)
    for path in duels:
        log = duel_log.read(path)
        label = duel_log.summary(log) if log else _("{name}, unreadable").format(name=path.name)
        menu.append_item(str(label), lambda path=path: duel_log_menu(path, return_to))

    replays = _replay_files()
    if replays:
        menu.append_item(_("Replay files saved from the server:"), None)
        for path in replays:
            label = _("{name}, {size} bytes").format(name=path.name, size=path.stat().st_size)
            menu.append_item(str(label), lambda path=path: replay_info_menu(path, return_to))

    menu.append_cancel_item(_("Back"), return_to)
    return menu


@utils.ui_function
def duel_log_menu(log_file, return_to=None):
    """Read a saved duel back, one line at a time."""
    log = duel_log.read(log_file)
    if log is None:
        utils.output(_("That duel could not be read."))
        return replay_viewer_menu.__wrapped__(return_to)

    lines = duel_log.lines(log)
    menu = VerticalMenu(str(log_file.name))
    menu.set_help_text(_(
        "Arrow keys walk through the duel, oldest first. Lines starting with "
        "You are your own choices. Escape goes back."
    ))
    menu.append_item(duel_log.summary(log), None)
    if not lines:
        menu.append_item(_("This duel has no entries."), None)
    for line in lines:
        menu.append_item(str(line), None)
    menu.append_item(_("Copy this duel to the clipboard"), lambda: _copy_lines(lines))
    menu.append_item(_("Delete this duel"), lambda: delete_replay(log_file, return_to))
    menu.append_cancel_item(_("Back"), lambda: replay_viewer_menu(return_to))
    return menu


def _copy_lines(lines):
    if not lines:
        utils.output(_("There is nothing to copy."))
        return
    if not wx.TheClipboard.Open():
        utils.output(_("Could not use the clipboard."))
        return
    try:
        wx.TheClipboard.SetData(wx.TextDataObject("\n".join(lines)))
        wx.TheClipboard.Flush()
    finally:
        wx.TheClipboard.Close()
    utils.output(_("Duel copied to the clipboard."))


@utils.ui_function
def replay_info_menu(replay_file, return_to=None):
    if not return_to:
        return_to = replay_viewer_menu
    stat = replay_file.stat()
    modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    menu = VerticalMenu(str(replay_file.name))
    menu.append_item(_("Replay file: {path}").format(path=str(replay_file)), None)
    menu.append_item(_("Size: {size} bytes").format(size=stat.st_size), None)
    menu.append_item(_("Saved: {date}").format(date=modified), None)
    if replay_file.suffix == ".yrp":
        menu.append_item(_("This is the core's own replay. Open it in EDOPro to watch it."), None)
    else:
        menu.append_item(_(
            "This is the local server's record of the duel. EDOPro cannot open it; "
            "the duel log above is the readable version."
        ), None)
    menu.append_item(_("Copy replay path"), lambda: copy_replay_path(replay_file))
    menu.append_item(_("Delete replay"), lambda: delete_replay(replay_file, return_to))
    menu.append_cancel_item(_("Back"), lambda: replay_viewer_menu(return_to))
    return menu


def copy_replay_path(replay_file):
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(str(replay_file)))
    wx.TheClipboard.Close()
    utils.output(_("Replay path copied to clipboard."))


def delete_replay(replay_file, return_to=None):
    replay_file.unlink(missing_ok=True)
    utils.output(_("Deleted."))
    return replay_viewer_menu.__wrapped__(return_to)
