import os
import sys
from unittest.mock import MagicMock

import pytest


def test_setup_logging_setup_and_debug_info(mocker, tmp_path):
    from core import utils

    log_file = tmp_path / "logs" / "app.log"
    old = tmp_path / "logs" / "old.log"
    old.parent.mkdir()
    old.write_text("old")
    old_time = 1
    mocker.patch("core.utils.variables.LOG_FILE", log_file)
    mocker.patch("core.utils.time.time", return_value=1209600 + 10)
    old.chmod(0o666)
    os.utime(old, (old_time, old_time))
    mocker.patch("core.utils.logging.basicConfig")
    utils.setup_logging()
    assert log_file.parent.exists()

    mocker.patch("core.utils.setup_logging")
    mocker.patch("core.utils.run_velopack")
    mocker.patch("core.utils.variables.APP_DATA_DIR", tmp_path / "data")
    utils.setup()
    assert (tmp_path / "data").exists()
    utils.setup()
    # Both runs look for an update: a fresh install needs one just as much as
    # an existing one does.
    assert utils.run_velopack.call_count == 2

    mocker.patch("core.utils.getattr", side_effect=lambda obj, name, default=None: True if name == "frozen" else getattr(obj, name, default))
    mocker.patch.object(sys, "_MEIPASS", "bundle", create=True)
    utils.log_debug_info()


def test_run_velopack_success_and_failure_paths(mocker):
    from core import utils

    app = MagicMock()
    mocker.patch("core.utils.velopack.App", return_value=app)
    response = MagicMock(url="https://github.com/YuGiOhAccess/YuGiOhAccess/releases/tag/v1")
    mocker.patch("core.utils.urllib.request.urlopen", return_value=response)
    manager = MagicMock()
    manager.check_for_updates.return_value = None
    mocker.patch("core.utils.velopack.UpdateManager", return_value=manager)
    utils.run_velopack()
    app.run.assert_called_once()
    manager.check_for_updates.assert_called_once()

    manager.check_for_updates.return_value = "update"
    utils.run_velopack()
    manager.download_updates.assert_called_with("update")
    manager.apply_updates_and_restart.assert_called_with("update")

    mocker.patch("core.utils.urllib.request.urlopen", side_effect=utils.urllib.error.HTTPError("", 404, "", None, None))
    utils.run_velopack()
    mocker.patch("core.utils.urllib.request.urlopen", return_value=response)
    mocker.patch("core.utils.velopack.UpdateManager", side_effect=Exception("bad"))
    utils.run_velopack()


def test_dev_options_validation_and_small_helpers(mocker):
    from core import utils

    parser = MagicMock()
    opts = MagicMock(server=1, action=None, id=None, password=None)
    mocker.patch("core.utils.variables.DEV_OPTIONS", opts)
    utils.validate_dev_options(parser)
    parser.error.assert_called_with("--server requires --action")

    parser.reset_mock()
    opts.action = "join"
    utils.validate_dev_options(parser)
    parser.error.assert_called_with("--action join requires --id")

    parser.reset_mock()
    opts.action = "create"
    opts.id = 1
    utils.validate_dev_options(parser)
    parser.error.assert_called_with("--action create requires --password")

    assert utils.guess_items_in(["Alice", "Alfred", "Bob"], "Al", "Bob") == ["Alfred", "Alice"]
    assert utils.guess_items_in(["Alice"], "Alice", "me") == ["Alice"]
    assert utils.extract_trailing_numbers("zone12") == 12
    assert utils.extract_trailing_numbers("zone") is None
    assert utils.version_string_to_pretty("1.0a1b2rc3")
    assert utils.sanitize_filename(" bad:name ?.json ") == "bad_name_.json"

    mocker.patch("core.utils.variables.IS_FROZEN", True)
    mocker.patch("core.utils.validate_dev_options")
    mocker.patch("core.utils.argparse.ArgumentParser.parse_args", return_value=MagicMock(help=False))
    utils.parse_dev_options()
    utils.validate_dev_options.assert_called()
    mocker.patch("core.utils.argparse.ArgumentParser.parse_args", return_value=MagicMock(help=True))
    mocker.patch("core.utils.argparse.ArgumentParser.print_help")
    with pytest.raises(SystemExit):
        utils.parse_dev_options()


def test_ui_and_handler_decorators_and_output(mocker):
    from core import utils

    frame = MagicMock()
    mocker.patch("core.utils.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("core.utils.wx.GetApp", return_value=MagicMock(IsActive=MagicMock(return_value=True)))

    def make_ui():
        return "ui"

    wrapped = utils.ui_function(make_ui)
    assert wrapped() is None
    # Recorded when the builder runs, not when it is decorated.
    assert utils.get_last_ui_function() is make_ui
    frame.pop_ui.assert_called()
    frame.push_ui.assert_called_with("ui")

    def no_ui():
        return None

    assert utils.ui_function(no_ui)() is not None
    assert utils.get_ui_stack() is frame
    frame.get_main_ui.return_value = "main"
    assert utils.get_main_menu_function() == "main"
    utils.refresh_ui()
    frame.refresh_ui.assert_called_once_with(None)
    rebuild = MagicMock()
    utils.refresh_ui(rebuild)
    frame.refresh_ui.assert_called_with(rebuild)
    utils.output("hello", interrupt=True)
    frame.output.assert_called_with("hello", True)

    mocker.patch("core.utils.variables.config", MagicMock(get=MagicMock(return_value=True)))
    mocker.patch("core.utils.wx.CallLater")
    utils.provide_tooltip("tip")
    utils.wx.CallLater.assert_called()

    manager = MagicMock()
    mocker.patch("core.utils.discord_presence.DiscordPresenceManager", return_value=manager)
    mocker.patch("core.utils.variables.DISCORD_PRESENCE_MANAGER", None)
    assert utils.get_discord_presence_manager() is manager
    manager.start.assert_called_once()

    errors = []
    utils.packet_handlers[-1] = lambda e, packet_id, func, *args, **kwargs: errors.append((packet_id, str(e)))

    @utils.packet_handler(99999)
    def bad_packet():
        raise ValueError("bad")

    bad_packet()
    assert errors[-1][0] == 99999

    utils.duel_message_handlers[-1] = lambda e, msg_id, func, *args, **kwargs: errors.append((msg_id, str(e)))

    @utils.duel_message_handler(88888)
    def bad_msg():
        raise ValueError("bad-msg")

    bad_msg()
    assert errors[-1][0] == 88888

    utils.packet_handlers[-1] = MagicMock(side_effect=RuntimeError("error-handler"))
    output = mocker.patch("core.utils.output")

    @utils.packet_handler(77777)
    def bad_packet_without_usable_error_handler():
        raise ValueError("packet")

    assert bad_packet_without_usable_error_handler() is None
    output.assert_called()


def test_repo_update_helpers(mocker, tmp_path):
    from core import utils

    missing = tmp_path / "missing"
    assert utils._repo_not_valid(missing) is True
    file_path = tmp_path / "file"
    file_path.write_text("x")
    assert utils._repo_not_valid(file_path) is True
    empty = tmp_path / "empty"
    empty.mkdir()
    assert utils._repo_not_valid(empty) is True
    (empty / "x").write_text("x")
    assert utils._repo_not_valid(empty) is None

    response = MagicMock()
    response.json.return_value = {"updated_at": "new"}
    response.raise_for_status.return_value = None
    mocker.patch("core.utils.requests.get", return_value=response)
    assert utils._should_redownload_repo("org/repo", empty) == (True, "new")
    (empty / "last_downloaded.txt").write_text("new")
    assert utils._should_redownload_repo("org/repo", empty) == (False, "new")

    http_error = utils.requests.HTTPError()
    http_error.response = MagicMock(status_code=403)
    response.raise_for_status.side_effect = http_error
    assert utils._should_redownload_repo("org/repo", empty) == (False, "new")
    response.raise_for_status.side_effect = utils.requests.RequestException("net")
    assert utils._should_redownload_repo("org/repo", empty) == (True, "")

    mocker.patch("core.utils._should_redownload_repo", return_value=(False, "date"))
    assert utils.update_data_repo("name", "org/repo", empty) is True
    mocker.patch("core.utils._should_redownload_repo", side_effect=Exception("boom"))
    assert utils.update_data_repo("name", "org/repo", empty) is False
