from datetime import datetime
from pathlib import Path

import wx

from core import utils, variables
from core.i18n import _
from ui.base_ui import VerticalMenu


def get_replay_dir():
    return Path(variables.APP_DATA_DIR) / "replays"


def save_replay_packet(client, packet_data, new=False):
    replay_dir = get_replay_dir()
    replay_dir.mkdir(parents=True, exist_ok=True)
    replay_file = getattr(client.memory, "replay_file", None)
    if new or not replay_file:
        room_id = getattr(client, "room_id", None) or "unknown"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        replay_file = replay_dir / f"duel_{timestamp}_{room_id}.yrp"
        client.memory.replay_file = replay_file
        replay_file.write_bytes(b"")
    with open(replay_file, "ab") as replay:
        replay.write(bytes(packet_data))
    return replay_file


def finish_replay_recording(client=None):
    if client is not None and hasattr(client, "memory"):
        client.memory.replay_file = None


@utils.ui_function
def replay_viewer_menu(return_to=None):
    if not return_to:
        from ui.main_ui import main_menu_view
        return_to = main_menu_view
    replay_dir = get_replay_dir()
    replay_dir.mkdir(parents=True, exist_ok=True)
    menu = VerticalMenu(_("Replay Viewer"))
    files = sorted(
        [path for path in replay_dir.iterdir() if path.is_file()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        menu.append_item(_("No saved replays."), None)
    for replay_file in files:
        label = _("{name}, {size} bytes").format(name=replay_file.name, size=replay_file.stat().st_size)
        menu.append_item(str(label), lambda replay_file=replay_file: replay_info_menu(replay_file, return_to))
    menu.append_item(_("Back"), return_to)
    return menu


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
    menu.append_item(_("Read replay summary"), lambda: read_replay_summary(replay_file))
    menu.append_item(_("Copy replay as hex"), lambda: copy_replay_hex(replay_file))
    menu.append_item(_("Copy replay path"), lambda: copy_replay_path(replay_file))
    menu.append_item(_("Delete replay"), lambda: delete_replay(replay_file, return_to))
    menu.append_item(_("Back"), lambda: replay_viewer_menu(return_to))
    return menu


def copy_replay_path(replay_file):
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(str(replay_file)))
    wx.TheClipboard.Close()
    utils.output(_("Replay path copied to clipboard."))


def read_replay_summary(replay_file):
    data = replay_file.read_bytes()
    if not data:
        utils.output(_("Replay is empty."))
        return
    preview = data[:32].hex(" ")
    utils.output(_("Replay size: {size} bytes. First bytes: {preview}").format(size=len(data), preview=preview))


def copy_replay_hex(replay_file):
    replay_hex = replay_file.read_bytes().hex()
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(replay_hex))
    wx.TheClipboard.Close()
    utils.output(_("Replay hex copied to clipboard."))


def delete_replay(replay_file, return_to=None):
    replay_file.unlink(missing_ok=True)
    utils.output(_("Replay deleted."))
    return replay_viewer_menu.__wrapped__(return_to)
