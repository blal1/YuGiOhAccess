import ctypes
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_dotdict_hasattr_and_missing_attribute():
    from core.dotdict import DotDict

    data = DotDict()
    data.value = 1

    assert data.value == 1
    assert data.__hasattr__("value") is True
    assert data.__hasattr__("missing") is False
    with pytest.raises(AttributeError):
        _ = data.missing


def test_i18n_language_listing_and_fallback(mocker, tmp_path, write_catalogue):
    from core import i18n

    mocker.patch("core.i18n._locale_dir", tmp_path / "missing")
    assert i18n.get_available_languages() == {"en": "English"}

    locale_dir = tmp_path / "locales"
    write_catalogue(locale_dir / "fr" / "LC_MESSAGES" / "yugiohaccess.mo")
    (locale_dir / "not_a_lang").write_text("x")
    mocker.patch("core.i18n._locale_dir", locale_dir)

    assert i18n.get_available_languages()["fr"] == "Français"
    mocker.patch("core.i18n.gettext.translation", side_effect=FileNotFoundError)
    i18n.setup("fr")
    assert i18n._("Hello") == "Hello"
    assert i18n.ngettext("card", "cards", 2) == "cards"
    assert i18n.pgettext("ctx", "Message") == "Message"


def test_global_error_and_game_msg_handlers(mocker):
    import ui
    from core import utils
    from game.edo import structs

    output = mocker.patch("ui.utils.output")
    mocker.patch("ui.wx.CallAfter")

    error = structs.ErrorMSG()
    error.msg = 5
    ui.handle_error_msg(MagicMock(), bytes(error), ctypes.sizeof(structs.ErrorMSG))
    assert output.called

    deck_error = structs.DeckErrrorMSG()
    ui.handle_error_msg(MagicMock(), bytes(deck_error), ctypes.sizeof(structs.DeckErrrorMSG))
    assert output.call_count >= 2

    ui.handle_game_msg(MagicMock(), b"\xff", 1)

    handler = MagicMock()
    utils.duel_message_handlers[1] = handler
    client = MagicMock()
    ui.handle_game_msg(client, b"\x01payload", 8)
    ui.wx.CallAfter.assert_called_with(handler, client, b"\x01payload", 8)


def test_duel_state_change_start_end_and_replay(mocker, tmp_path):
    from ui import duel_state_change_ui

    stack = MagicMock()
    mocker.patch("ui.duel_state_change_ui.utils.get_ui_stack", return_value=stack)
    presence = MagicMock()
    mocker.patch("ui.duel_state_change_ui.utils.get_discord_presence_manager", return_value=presence)
    output = mocker.patch("ui.duel_state_change_ui.utils.output")
    mocker.patch("ui.duel_state_change_ui.wx.CallLater")
    app = MagicMock()
    mocker.patch("ui.duel_state_change_ui.wx.GetApp", return_value=app)
    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)

    client = SimpleNamespace(memory=SimpleNamespace(), room_id=9)

    duel_state_change_ui.handle_duel_start(client, b"", 0)
    stack.clear_ui_stack.assert_called()
    presence.update_presence.assert_called_with(state="Duel Starting")

    duel_state_change_ui.handle_duel_end(client, b"", 0)
    stack.music_audio_manager.fade_out_all_audio.assert_called()
    assert duel_state_change_ui.wx.CallLater.call_count >= 3

    duel_state_change_ui.handle_new_replay(client, b"abc", 3)
    duel_state_change_ui.handle_replay(client, b"def", 3)
    assert client.memory.replay_file.read_bytes() == b"abcdef"
    assert output.called


def test_utils_error_wrappers_and_empty_filename(mocker):
    from core import utils

    assert utils.sanitize_filename("   ") == "_"

    packet_error = MagicMock()
    utils.packet_handlers[-1] = packet_error

    @utils.packet_handler(9999)
    def packet_handler():
        raise RuntimeError("packet")

    packet_handler()
    packet_error.assert_called_once()

    duel_error = MagicMock()
    utils.duel_message_handlers[-1] = duel_error

    @utils.duel_message_handler(9998)
    def duel_handler():
        raise RuntimeError("duel")

    duel_handler()
    duel_error.assert_called_once()

    del utils.packet_handlers[-1]
    del utils.duel_message_handlers[-1]
    output = mocker.patch("core.utils.output")

    @utils.packet_handler(9997)
    def packet_handler_without_error_handler():
        raise RuntimeError("packet")

    assert packet_handler_without_error_handler() is None
    output.assert_called()

    @utils.duel_message_handler(9996)
    def duel_handler_without_error_handler():
        raise RuntimeError("duel")

    assert duel_handler_without_error_handler() is None
    output.assert_called()
