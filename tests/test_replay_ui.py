from types import SimpleNamespace

from tests.test_ui_flows_more import FakeMenu


def _log_entries():
    """A short duel's worth of history, as the speech log holds it."""
    from core import speech

    return [
        speech.LogEntry(100.0, "Duel starting", speech.Priority.INFO, True, speech.Kind.MESSAGE),
        speech.LogEntry(105.0, "Summon Blue-Eyes", speech.Priority.INFO, False, speech.Kind.ACTION),
        speech.LogEntry(160.0, "You win the duel!", speech.Priority.CRITICAL, True, speech.Kind.MESSAGE),
    ]


def test_a_finished_duel_is_saved_and_can_be_read_back(mocker, tmp_path):
    """The whole point of the viewer: play a duel, then review what happened."""
    from core import speech
    from ui import replay_ui

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.replay_ui.utils.output")
    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=_log_entries())

    saved = replay_ui.finish_replay_recording(SimpleNamespace(memory=SimpleNamespace(), room_id=42))
    assert saved is not None and saved.exists()

    # The duel is listed, and opening it reads the duel back line by line.
    menu = replay_ui.replay_viewer_menu.__wrapped__(lambda: None)
    assert any("3 entries" in str(item[0]) for item in menu.items)

    opened = replay_ui.duel_log_menu.__wrapped__(saved, lambda: None)
    spoken = [str(item[0]) for item in opened.items]
    assert any("Duel starting" in line for line in spoken)
    # The player's own choices are marked as theirs.
    assert any(line.startswith("00:05 You: Summon Blue-Eyes") for line in spoken)
    assert any("You win the duel!" in line for line in spoken)


def test_a_duel_with_nothing_in_it_is_not_saved(mocker, tmp_path):
    from core import speech
    from ui import replay_ui

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.utils.output")
    mocker.patch.object(speech.MESSAGE_LOG, "entries", return_value=[])

    assert replay_ui.record_duel_log(SimpleNamespace(memory=SimpleNamespace(), room_id=1)) is None


def test_an_unreadable_duel_log_does_not_take_the_viewer_down(mocker, tmp_path):
    from ui import replay_ui
    from game import duel_log

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.replay_ui.utils.output")
    broken = replay_ui.get_replay_dir() / f"duel_broken{duel_log.SUFFIX}"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_text("not json", encoding="utf-8")

    menu = replay_ui.replay_viewer_menu.__wrapped__(lambda: None)
    assert any("unreadable" in str(item[0]) for item in menu.items)

    replay_ui.duel_log_menu.__wrapped__(broken, lambda: None)
    replay_ui.utils.output.assert_any_call("That duel could not be read.")


def test_server_replay_files_are_kept_and_offered_separately(mocker, tmp_path):
    """A .yrp is the core's own file; we keep the bytes and say so."""
    from ui import replay_ui

    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.replay_ui.utils.output")
    client = SimpleNamespace(memory=SimpleNamespace(), room_id=123)

    replay_file = replay_ui.save_replay_packet(client, b"new", new=True)
    replay_ui.save_replay_packet(client, b"more")
    assert replay_file.read_bytes() == b"newmore"

    menu = replay_ui.replay_viewer_menu.__wrapped__(lambda: None)
    assert any("Replay files saved from the server" in str(item[0]) for item in menu.items)
    # Bytes we did not write ourselves are the core's, and keep the name that
    # says a program can open them.
    assert replay_file.suffix == ".yrp"

    mocker.patch("ui.replay_ui.wx.TheClipboard")
    mocker.patch("ui.replay_ui.wx.TextDataObject", side_effect=lambda text: text)
    info_menu = replay_ui.replay_info_menu.__wrapped__(replay_file, lambda: None)
    assert any("Size" in str(item[0]) for item in info_menu.items)

    replay_ui.copy_replay_path(replay_file)
    replay_ui.wx.TheClipboard.SetData.assert_called_once_with(str(replay_file))

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
