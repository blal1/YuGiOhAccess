from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.test_ui_flows_more import FakeMenu


def test_save_replay_packet_and_viewer(mocker, tmp_path):
    from ui import replay_ui

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.VerticalMenu", FakeMenu)
    client = SimpleNamespace(memory=SimpleNamespace(), room_id=123)

    replay_file = replay_ui.save_replay_packet(client, b"new", new=True)
    replay_ui.save_replay_packet(client, b"more")

    assert replay_file.read_bytes() == b"newmore"
    menu = replay_ui.replay_viewer_menu.__wrapped__(lambda: None)
    assert any("duel_" in str(item[0]) for item in menu.items)

    mocker.patch("ui.replay_ui.wx.TheClipboard")
    mocker.patch("ui.replay_ui.wx.TextDataObject", side_effect=lambda text: text)
    mocker.patch("ui.replay_ui.utils.output")
    info_menu = replay_ui.replay_info_menu.__wrapped__(replay_file, lambda: None)
    assert any("Size" in str(item[0]) for item in info_menu.items)
    replay_ui.copy_replay_path(replay_file)
    replay_ui.wx.TheClipboard.SetData.assert_called_once_with(str(replay_file))

    replay_ui.wx.TheClipboard.SetData.reset_mock()
    replay_ui.copy_replay_hex(replay_file)
    replay_ui.wx.TheClipboard.SetData.assert_called_once_with(replay_file.read_bytes().hex())

    replay_ui.read_replay_summary(replay_file)
    replay_ui.utils.output.assert_any_call("Replay hex copied to clipboard.")
    assert any("Replay size" in call.args[0] for call in replay_ui.utils.output.call_args_list)

    empty = tmp_path / "empty.yrp"
    empty.write_bytes(b"")
    replay_ui.read_replay_summary(empty)
    replay_ui.utils.output.assert_any_call("Replay is empty.")

    deleted_menu = replay_ui.delete_replay(replay_file, lambda: None)
    assert not replay_file.exists()
    assert deleted_menu.items


def test_replay_packet_handlers_save_data(mocker, tmp_path):
    from ui import duel_state_change_ui

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.duel_state_change_ui.utils.output")
    client = SimpleNamespace(memory=SimpleNamespace(), room_id=7)

    duel_state_change_ui.handle_new_replay(client, b"abc", 3)
    duel_state_change_ui.handle_replay(client, b"def", 3)

    replay_file = client.memory.replay_file
    assert replay_file.read_bytes() == b"abcdef"
