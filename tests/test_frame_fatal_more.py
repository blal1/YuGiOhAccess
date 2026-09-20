from unittest.mock import MagicMock


def test_fatal_exception_hooks_dialog_and_sound(mocker, tmp_path):
    import sys
    from ui import fatal_exception_ui

    mocker.patch("ui.fatal_exception_ui.variables.IS_FROZEN", False)
    fatal_exception_ui.attach_exception_hook()
    assert sys.excepthook is fatal_exception_ui._custom_exception_hook
    mocker.patch("ui.fatal_exception_ui.variables.IS_FROZEN", True)
    fatal_exception_ui.attach_exception_hook()
    assert sys.excepthook is fatal_exception_ui._custom_exception_hook_frozen

    log_file = tmp_path / "log.txt"
    log_file.write_text("logs")
    mocker.patch("ui.fatal_exception_ui.variables.LOG_FILE", log_file)
    assert fatal_exception_ui._retrieve_log_content() == "logs"
    mocker.patch("ui.fatal_exception_ui.variables.LOG_FILE", tmp_path / "missing.log")
    assert "Log not available" in fatal_exception_ui._retrieve_log_content()

    audio = MagicMock()
    mocker.patch("ui.fatal_exception_ui.AudioManager", return_value=audio)
    mocker.patch("ui.fatal_exception_ui.time.sleep")
    fatal_exception_ui._play_error_sound()
    audio.play_audio.assert_called_with("error.wav")

    thread_cls = mocker.patch("ui.fatal_exception_ui.threading.Thread")
    fatal_exception_ui._custom_exception_hook_frozen(RuntimeError, RuntimeError("x"), None)
    thread_cls.return_value.start.assert_called_once()

    dialog = MagicMock()
    mocker.patch("ui.fatal_exception_ui.wx.lib.dialogs.ScrolledMessageDialog", return_value=dialog)
    try:
        raise ValueError("boom")
    except ValueError as exc:
        fatal_exception_ui._custom_exception_hook(ValueError, exc, exc.__traceback__)
    dialog.ShowModal.assert_called_once()
    dialog.Destroy.assert_called_once()


def _frame():
    from ui.frame import YuGiOhAccessFrame

    frame = YuGiOhAccessFrame.__new__(YuGiOhAccessFrame)
    frame.ui_stack = []
    frame.game_area = MagicMock()
    frame.main_sizer = MagicMock()
    frame.Fit = MagicMock()
    frame.Layout = MagicMock()
    frame.Close = MagicMock()
    frame.sound_effects_audio_manager = MagicMock()
    frame.music_audio_manager = MagicMock()
    frame.sr_output = MagicMock()
    return frame


def test_frame_stack_about_close_output_and_keys(mocker, tmp_path):
    from ui import frame as frame_module

    frame = _frame()
    ui1 = MagicMock()
    ui2 = MagicMock()
    frame.push_ui(ui1)
    frame.game_area.Hide.assert_called_once()
    frame.main_sizer.Hide.assert_any_call(frame.game_area)
    frame.push_ui(ui2)
    ui1.Hide.assert_called_once()
    assert frame.prettify_ui_stack() == [str(ui1), str(ui2)]
    frame.pop_ui()
    ui2.Hide.assert_called_once()
    ui1.Show.assert_called()
    frame.main_sizer.Show.assert_any_call(ui1)
    ui1.SetFocus.assert_called()
    frame.clear_ui_stack()
    assert frame.ui_stack == []
    frame.game_area.Show.assert_called()
    frame.pop_ui()

    mocker.patch("ui.frame.main_ui.main_menu_view", return_value="main")
    assert frame.get_main_ui() == "main"
    refresh = MagicMock()
    frame.refresh_ui(refresh)
    refresh.assert_called_once()

    info = MagicMock()
    mocker.patch("ui.frame.wx.adv.AboutDialogInfo", return_value=info)
    about = mocker.patch("ui.frame.wx.adv.AboutBox")
    mocker.patch("ui.frame.utils.version_string_to_pretty", return_value="1.0")
    mocker.patch("ui.frame.variables.APP_VERSION", "1.0")
    frame.on_about(MagicMock())
    info.SetName.assert_called_with("YuGiOhAccess")
    about.assert_called_with(info)

    frame.on_exit(MagicMock())
    frame.Close.assert_called_once()
    event = MagicMock()
    frame.on_close(event)
    frame.sound_effects_audio_manager.stop_all_audio.assert_called()
    frame.music_audio_manager.stop_all_audio.assert_called()
    event.Skip.assert_called()

    frame.output("hello", True)
    frame.sr_output.output.assert_called_with("hello", True)

    sound_dir = tmp_path / "sounds" / "duel" / "draw"
    sound_dir.mkdir(parents=True)
    (sound_dir / "a.wav").write_bytes(b"")
    effect_dir = tmp_path / "sounds" / "duel"
    (effect_dir / "start.ogg").write_bytes(b"")
    music_dir = tmp_path / "sounds" / "music" / "start"
    music_dir.mkdir(parents=True)
    (music_dir / "m.ogg").write_bytes(b"")
    mocker.patch("ui.frame.variables.LOCAL_DATA_DIR", tmp_path)
    mocker.patch("ui.frame.random.choice", side_effect=lambda items: list(items)[0])
    frame.play_random_duel_sound_effect_in_directory("draw", x=1)
    frame.sound_effects_audio_manager.play_audio.assert_any_call("duel/draw/a.wav", x=1, y=0.0, z=0.0)
    frame.play_duel_sound_effect("start")
    frame.sound_effects_audio_manager.play_audio.assert_any_call("duel/start.ogg", x=0.0, y=0.0, z=0.0)
    frame.play_duel_sound_effect("missing")
    frame.play_main_music()
    frame.music_audio_manager.play_audio.assert_called_with("music/start/m.ogg", looping=True)

    event = MagicMock()
    for key, manager, method in [
        (frame_module.wx.WXK_F5, frame.sound_effects_audio_manager, "decrease_volume"),
        (frame_module.wx.WXK_F6, frame.sound_effects_audio_manager, "increase_volume"),
        (frame_module.wx.WXK_F7, frame.music_audio_manager, "decrease_volume"),
        (frame_module.wx.WXK_F8, frame.music_audio_manager, "increase_volume"),
    ]:
        event.GetKeyCode.return_value = key
        frame.on_key_down(event)
        getattr(manager, method).assert_called()


def test_frame_init_wires_ui_without_starting_client(mocker):
    from ui import frame as frame_module

    sound_manager = MagicMock()
    music_manager = MagicMock()
    audio_cls = mocker.patch("ui.frame.AudioManager", side_effect=[sound_manager, music_manager])
    mocker.patch("ui.frame.output.output", "screenreader")
    panel = MagicMock()
    mocker.patch("ui.frame.wx.Panel", return_value=panel)
    menubar = MagicMock()
    menu = MagicMock()
    menu.Append.side_effect = ["about-item", "exit-item"]
    mocker.patch("ui.frame.wx.MenuBar", return_value=menubar)
    mocker.patch("ui.frame.wx.Menu", return_value=menu)
    sizer = MagicMock()
    mocker.patch("ui.frame.wx.BoxSizer", return_value=sizer)
    mocker.patch.object(frame_module.YuGiOhAccessFrame, "Bind", MagicMock())
    mocker.patch.object(frame_module.YuGiOhAccessFrame, "SetMenuBar", MagicMock())
    mocker.patch.object(frame_module.YuGiOhAccessFrame, "SetSizer", MagicMock())
    mocker.patch.object(frame_module.YuGiOhAccessFrame, "Maximize", MagicMock())
    mocker.patch.object(frame_module.YuGiOhAccessFrame, "Show", MagicMock())
    mocker.patch("ui.frame.wx.Frame.__init__", return_value=None)
    dummy_ui = MagicMock()

    def fake_play_main_music(self):
        self.ui_stack.append(dummy_ui)

    mocker.patch.object(frame_module.YuGiOhAccessFrame, "play_main_music", fake_play_main_music)
    mocker.patch("ui.frame.data_updater_ui.ensure_yugioh_data_is_up_to_date")

    created = frame_module.YuGiOhAccessFrame()

    assert created.sr_output == "screenreader"
    assert created.sound_effects_audio_manager is sound_manager
    assert created.music_audio_manager is music_manager
    assert audio_cls.call_args_list[0].args == ("sound_effects_volume",)
    assert audio_cls.call_args_list[1].args == ("music_volume",)
    panel.Fit.assert_called_once()
    sizer.Add.assert_called_with(panel, 1, frame_module.wx.EXPAND)
    assert created.ui_stack[-1] is dummy_ui
    dummy_ui.SetFocus.assert_called_once()


def test_app_and_output_modules(mocker):
    import importlib
    from ui.app import YuGiOhAccessAPP

    mocker.patch("ui.app.wx.App.OnInit", return_value=True)
    app = YuGiOhAccessAPP.__new__(YuGiOhAccessAPP)
    assert app.OnInit() is True

    auto = MagicMock()
    mocker.patch("accessible_output3.outputs.auto.Auto", return_value=auto)
    import ui.output as output
    importlib.reload(output)
    assert output.output is auto

    # ui/output2.py was a duplicate of this backend and has been folded in.
    popen = mocker.patch("ui.output.subprocess.Popen")
    mocker.patch("ui.output.platform.system", return_value="Darwin")
    output.VoiceOverOutput._instance = None
    singleton = output.VoiceOverOutput()
    singleton.output('say "hi"')
    popen.return_value.stdin.write.assert_called()
    written = popen.return_value.stdin.write.call_args.args[0].decode("utf-8")
    assert '\\"hi\\"' in written
    assert output.VoiceOverOutput() is singleton
    output.VoiceOverOutput._instance = None
