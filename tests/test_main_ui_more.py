from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.test_ui_flows_more import FakeMenu, FakeStatus


def _patch_main(mocker):
    from ui import main_ui

    mocker.patch("ui.main_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.main_ui.StatusMessage", FakeStatus)
    mocker.patch("ui.main_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    stack = MagicMock()
    stack.music_audio_manager.get_volume.return_value = 0.5
    stack.sound_effects_audio_manager.get_volume.return_value = 0.4
    mocker.patch("ui.main_ui.utils.get_ui_stack", return_value=stack)
    mocker.patch("ui.main_ui.utils.output")
    main_ui.variables.config = MagicMock()
    main_ui.variables.config.get.side_effect = lambda key, default=None: {
        "nickname": "Tester",
        "first_time_run": False,
        "enable_hints": True,
        "screenreader_output_only_on_application_focus": False,
        "helper_zones": True,
        "rock_paper_scissors_bot_behavior": "scissors",
        "enable_bot_chat": True,
        "ui_language": "fr",
        "language": "english",
    }.get(key, default)
    language_handler = MagicMock()
    language_handler.languages = {"english": {}, "french": {}, "spanish": {}}
    language_handler.is_loaded.side_effect = lambda language: language in language_handler.languages
    main_ui.variables.LANGUAGE_HANDLER = language_handler
    main_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None)
    main_ui.variables.IS_FROZEN = False
    main_ui.variables.APP_VERSION = "1.0"
    return main_ui, stack


def test_first_ui_branches_and_open_deck_editor(mocker):
    main_ui, _stack = _patch_main(mocker)
    mocker.patch("ui.main_ui.main_menu_view")
    mocker.patch("ui.main_ui.first_ui_help_info")

    main_ui.variables.config.get.side_effect = lambda key, default=None: True if key == "first_time_run" else default
    main_ui.first_ui.__wrapped__()
    main_ui.variables.config.set.assert_called_with("first_time_run", False)
    main_ui.first_ui_help_info.assert_called_once()

    main_ui.first_ui_help_info.reset_mock()
    main_ui.variables.config.get.side_effect = lambda key, default=None: False if key == "first_time_run" else default
    main_ui.first_ui.__wrapped__()
    main_ui.main_menu_view.assert_called_once()

    mocker.patch("ui.main_ui.deck_editor_ui.deck_editor_main_menu")
    main_ui._open_deck_editor()
    main_ui.deck_editor_ui.deck_editor_main_menu.assert_called_with(main_ui.main_menu_view)


def test_main_menu_dev_server_and_windbot_menus(mocker):
    main_ui, _stack = _patch_main(mocker)
    mocker.patch("ui.main_ui.server_ui.server_selection_menu")
    main_ui.variables.DEV_OPTIONS = SimpleNamespace(server=1)
    assert main_ui.main_menu_view.__wrapped__() is None
    main_ui.server_ui.server_selection_menu.assert_called_once()

    main_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None)
    mocker.patch("ui.main_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    menu = main_ui.main_menu_view.__wrapped__()
    assert any(item[0] == "Make Windbot deck" for item in menu.items)

    windbot = main_ui.make_windbot_deck.__wrapped__()
    assert any(item[0] == "Done" for item in windbot.items)
    ydke = main_ui.make_deck_string_from_windbot_deck.__wrapped__()
    assert any(item[0] == "Done" for item in ydke.items)


def test_settings_menu_all_selection_branches_and_language_change(mocker):
    main_ui, _stack = _patch_main(mocker)
    mocker.patch("core.i18n.get_available_languages", return_value={"en": "English", "fr": "Français"})
    setup = mocker.patch("core.i18n.setup")

    for behavior in ("random", "rock", "paper", "scissors", "unknown"):
        main_ui.variables.config.get.side_effect = lambda key, default=None, behavior=behavior: {
            "enable_hints": True,
            "screenreader_output_only_on_application_focus": False,
            "helper_zones": True,
            "rock_paper_scissors_bot_behavior": behavior,
            "enable_bot_chat": True,
            "ui_language": "missing",
            "language": "french",
        }.get(key, default)
        menu = main_ui.settings_menu.__wrapped__(MagicMock())
        assert any(item[0] == "Done" for item in menu.items)

    # Trigger checkbox callback branches captured in FakeMenu.
    event = MagicMock()
    event.IsChecked.return_value = False
    for item in menu.items:
        callback = item[1]
        if callable(callback) and item[0].__class__.__name__ == "type":
            callback(event)

    # Trigger UI language callback from the choice Bind call.
    choice_control = [item[4] for item in menu.items if item[3].get("label") == "UI Language"][0]
    calls = choice_control.Bind.call_args_list
    lang_callback = calls[0].args[1]
    lang_event = MagicMock()
    lang_event.GetEventObject.return_value.GetSelection.return_value = 1
    lang_callback(lang_event)
    main_ui.variables.config.set.assert_any_call("ui_language", "fr")
    setup.assert_called_with("fr")

    card_language_choice = [item[4] for item in menu.items if item[3].get("label") == "Card catalog language"][0]
    card_language_item = [item for item in menu.items if item[3].get("label") == "Card catalog language"][0]
    assert card_language_item[3]["choices"] == ["English", "French", "Spanish"]
    card_callback = card_language_choice.Bind.call_args_list[0].args[1]
    card_event = MagicMock()
    card_event.GetEventObject.return_value.GetSelection.return_value = 2
    card_callback(card_event)
    main_ui.variables.config.set.assert_any_call("language", "spanish")
    main_ui.variables.LANGUAGE_HANDLER.set_primary_language.assert_called_with("spanish")

    main_ui.set_card_catalog_language("missing")
    assert any("not available" in str(call) for call in main_ui.utils.output.call_args_list)


def test_card_catalog_language_fallback_branches(mocker):
    main_ui, _stack = _patch_main(mocker)

    main_ui.variables.LANGUAGE_HANDLER = None
    assert main_ui.get_card_catalog_language_names() == ["english"]
    assert main_ui.get_card_catalog_language_display_name("custom_language") == "Custom Language"

    event = MagicMock()
    event.GetEventObject.return_value.GetSelection.return_value = 99
    setter = mocker.patch("ui.main_ui.set_card_catalog_language")
    main_ui.on_card_language_change(event)
    setter.assert_not_called()

    handler = MagicMock()
    handler.languages = {"english": {}}
    handler.is_loaded.return_value = True
    main_ui.variables.LANGUAGE_HANDLER = handler
    main_ui.variables.config.get.side_effect = lambda key, default=None: {
        "enable_hints": True,
        "screenreader_output_only_on_application_focus": False,
        "helper_zones": True,
        "rock_paper_scissors_bot_behavior": "random",
        "enable_bot_chat": True,
        "ui_language": "en",
        "language": "missing",
    }.get(key, default)

    menu = main_ui.settings_menu.__wrapped__(MagicMock())
    card_language_choice = [item[4] for item in menu.items if item[3].get("label") == "Card catalog language"][0]
    card_language_choice.SetSelection.assert_called_with(0)
