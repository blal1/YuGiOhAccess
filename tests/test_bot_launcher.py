from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_bot_launcher_converts_client_version_struct_to_windbot_int():
    from bot import launcher
    from game.edo import structs

    version = structs.ClientVersion((1, 2), (3, 4))

    assert launcher._edo_client_version_to_int(version) == 0x04030201
    assert launcher._edo_client_version_to_int(123) == 123


def test_bot_launcher_converts_visible_deck_file_names_to_windbot_keys():
    from bot import launcher

    assert launcher._deck_file_name_to_windbot_key("AI_Blackwing") == "Blackwing"
    assert launcher._deck_file_name_to_windbot_key("AI_BlueEyes.ydk") == "Blue-Eyes"
    assert launcher._deck_file_name_to_windbot_key("AI_DarkMagician") == "DarkMagician"
    assert launcher._deck_file_name_to_windbot_key("AI_Dragun") == "Dragun"
    assert launcher._deck_file_name_to_windbot_key("AI_Custom") == "Custom"
    assert launcher._deck_file_name_to_windbot_key("") == ""


def test_bot_launcher_skips_uninitialized_local_data_dir(mocker, tmp_path):
    from bot import launcher

    asset_dir = tmp_path / "data" / "bot"
    asset_dir.mkdir(parents=True)
    (asset_dir / "WindBot.Desktop.dll").write_text("", encoding="utf-8")
    mocker.patch.object(launcher.variables, "LOCAL_DATA_DIR", None)
    mocker.patch.object(launcher.variables, "EXECUTABLE_DIR", tmp_path)
    mocker.patch.object(launcher.variables, "APP_DATA_DIR", str(tmp_path / "appdata"))

    assert launcher._find_bot_asset_path() == asset_dir
    assert launcher._find_bot_database_paths() == []


def test_bot_launcher_reports_missing_assets_when_local_data_dir_unset(mocker, tmp_path):
    from bot import launcher

    mocker.patch.object(launcher.variables, "LOCAL_DATA_DIR", None)
    mocker.patch.object(launcher.variables, "EXECUTABLE_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        launcher._find_bot_asset_path()


def test_launch_bot_for_room_passes_windbot_safe_arguments(mocker):
    from bot import launcher
    from game.edo import structs

    mocker.patch("bot.launcher._ensure_engine")
    launch_bot = mocker.patch("bot.engine.launch_bot")
    mocker.patch.object(launcher.variables, "edo_client_version", structs.ClientVersion((41, 0), (11, 0)))
    launcher.variables.config = MagicMock()
    launcher.variables.config.get.side_effect = lambda key, default=None: {
        "rock_paper_scissors_bot_behavior": "paper",
        "enable_bot_chat": True,
    }.get(key, default)
    client = SimpleNamespace(
        server=SimpleNamespace(address="127.0.0.1", lobby_port=7933),
        room=SimpleNamespace(roomid=12345),
    )

    launcher.launch_bot_for_room(client, deck="AI_BlueEyes.ydk")

    launch_bot.assert_called_once_with(
        host="127.0.0.1",
        port=7933,
        # A string: WindBot reads every launch field as one, and a number
        # makes it discard the whole payload.
        room_info="12345",
        deck="Blue-Eyes",
        name="WindBot",
        hand=3,
        chat=True,
        version=720937,
    )


def test_launch_bot_for_room_respects_the_chat_setting(mocker):
    """The setting is the master switch; the caller can only be stricter."""
    from bot import launcher
    from game.edo import structs

    mocker.patch("bot.launcher._ensure_engine")
    launch_bot = mocker.patch("bot.engine.launch_bot")
    mocker.patch.object(launcher.variables, "edo_client_version", structs.ClientVersion((41, 0), (11, 0)))
    client = SimpleNamespace(
        server=SimpleNamespace(address="127.0.0.1", lobby_port=7933),
        room=SimpleNamespace(roomid=12345),
    )

    def configure(enable_bot_chat):
        launcher.variables.config = MagicMock()
        launcher.variables.config.get.side_effect = lambda key, default=None: {
            "rock_paper_scissors_bot_behavior": "random",
            "enable_bot_chat": enable_bot_chat,
        }.get(key, default)

    # Unticking the setting silences the bot even though the caller defaults
    # to wanting chat.
    configure(False)
    launcher.launch_bot_for_room(client, deck="AI_BlueEyes.ydk")
    assert launch_bot.call_args.kwargs["chat"] is False

    # And a caller that asks for silence gets it whatever the setting says.
    configure(True)
    launcher.launch_bot_for_room(client, deck="AI_BlueEyes.ydk", chat=False)
    assert launch_bot.call_args.kwargs["chat"] is False
