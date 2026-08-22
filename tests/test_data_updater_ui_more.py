from unittest.mock import MagicMock


def _repo(tmp_path, name, required=True, cached=True):
    path = tmp_path / name
    if cached:
        path.mkdir()
        (path / "marker").write_text("cached", encoding="utf-8")
    return {"name": name, "local_path": path, "required": required}


def test_has_cached_data_ignores_optional_repositories(tmp_path, mocker):
    from ui import data_updater_ui

    required = _repo(tmp_path, "required", required=True, cached=True)
    optional_missing = {"name": "optional", "local_path": tmp_path / "optional", "required": False}
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required, optional_missing])

    assert data_updater_ui._has_cached_data() is True

    required["local_path"] = tmp_path / "missing"
    assert data_updater_ui._has_cached_data() is False


def test_update_data_thread_success_allows_optional_failure(tmp_path, mocker):
    from ui import data_updater_ui

    required = _repo(tmp_path, "cards", required=True, cached=False)
    optional = _repo(tmp_path, "languages", required=False, cached=False)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required, optional])
    mocker.patch.object(data_updater_ui.variables, "LANGUAGE_HANDLER", MagicMock())
    mocker.patch("ui.data_updater_ui.wx.Yield")
    call_after = mocker.patch("ui.data_updater_ui.wx.CallAfter", side_effect=lambda func, *args: func(*args))
    result_ui = mocker.patch("ui.data_updater_ui.RESULT_UI")
    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")
    start_background = mocker.patch("ui.data_updater_ui.start_background_catalog_update")

    def update_data_repo(**repo):
        return repo["name"] == "cards"

    mocker.patch("ui.data_updater_ui.utils.update_data_repo", side_effect=update_data_repo)

    data_updater_ui._update_data_thread()

    refresh.assert_called_once()
    start_background.assert_called_once()
    call_after.assert_called()
    result_ui.assert_called_once()


def test_update_data_thread_uses_cached_data_when_required_update_fails(tmp_path, mocker):
    from ui import data_updater_ui

    required = _repo(tmp_path, "cards", required=True, cached=True)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required])
    mocker.patch.object(data_updater_ui.variables, "LANGUAGE_HANDLER", MagicMock())
    mocker.patch("ui.data_updater_ui.wx.Yield")
    mocker.patch("ui.data_updater_ui.utils.update_data_repo", return_value=False)
    warn = mocker.patch("ui.data_updater_ui._warn_cached_then_continue")
    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")
    start_background = mocker.patch("ui.data_updater_ui.start_background_catalog_update")
    mocker.patch("ui.data_updater_ui.wx.CallAfter", side_effect=lambda func, *args: func(*args))

    data_updater_ui._update_data_thread()

    refresh.assert_called_once()
    start_background.assert_called_once()
    warn.assert_called_once()


def test_update_data_thread_reports_failure_without_cache(tmp_path, mocker):
    from ui import data_updater_ui

    required = _repo(tmp_path, "cards", required=True, cached=False)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required])
    mocker.patch("ui.data_updater_ui.wx.Yield")
    mocker.patch("ui.data_updater_ui.utils.update_data_repo", side_effect=RuntimeError("offline"))
    failed = mocker.patch("ui.data_updater_ui.failed_data_update")
    mocker.patch("ui.data_updater_ui.wx.CallAfter", side_effect=lambda func, *args: func(*args))

    data_updater_ui._update_data_thread()

    failed.assert_called_once()


def test_warn_and_failed_menus(mocker):
    from tests.test_ui_flows_more import FakeMenu
    from ui import data_updater_ui

    mocker.patch("ui.data_updater_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.data_updater_ui.utils.output")
    result_ui = mocker.patch("ui.data_updater_ui.RESULT_UI")
    data_updater_ui._warn_cached_then_continue.__wrapped__()
    data_updater_ui.utils.output.assert_called_once()
    result_ui.assert_called_once()

    top = MagicMock()
    mocker.patch("ui.data_updater_ui.wx.GetTopLevelWindows", return_value=[top])
    menu = data_updater_ui.failed_data_update.__wrapped__()
    labels = [item[0] for item in menu.items]
    assert "Retry" in labels
    assert "Exit" in labels


def test_refresh_loaded_catalog_data_reconnects_language_and_reloads_banlists(mocker):
    from ui import data_updater_ui

    handler = MagicMock()
    handler.is_loaded.side_effect = lambda language: language == "french"
    mocker.patch.object(data_updater_ui.variables, "LANGUAGE_HANDLER", handler)
    config = MagicMock()
    config.get.return_value = "french"
    mocker.patch.object(data_updater_ui.variables, "config", config)
    manager = MagicMock()
    banlist_manager = mocker.patch("game.edo.banlists.BanlistManager", return_value=manager)

    data_updater_ui._refresh_loaded_catalog_data()

    handler.add_available_languages.assert_called_once()
    handler.connect_all_databases.assert_called_once()
    handler.set_primary_language.assert_called_once_with("french")
    banlist_manager.assert_called_once()
    manager.reload.assert_called_once()


def test_refresh_loaded_catalog_data_falls_back_to_english(mocker):
    from ui import data_updater_ui

    handler = MagicMock()
    handler.is_loaded.side_effect = lambda language: language == "english"
    mocker.patch.object(data_updater_ui.variables, "LANGUAGE_HANDLER", handler)
    config = MagicMock()
    config.get.return_value = "missing"
    mocker.patch.object(data_updater_ui.variables, "config", config)
    mocker.patch("game.edo.banlists.BanlistManager", return_value=MagicMock())

    data_updater_ui._refresh_loaded_catalog_data()

    config.set.assert_called_once_with("language", "english")
    handler.set_primary_language.assert_called_once_with("english")


def test_run_background_catalog_update_refreshes_after_required_success(tmp_path, mocker):
    from ui import data_updater_ui

    data_updater_ui._background_catalog_refresh_pending = False
    required = _repo(tmp_path, "cards", required=True, cached=False)
    optional = _repo(tmp_path, "languages", required=False, cached=False)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required, optional])
    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")

    def update_data_repo(**repo):
        return repo["name"] == "cards"

    mocker.patch("ui.data_updater_ui.utils.update_data_repo", side_effect=update_data_repo)

    assert data_updater_ui._run_background_catalog_update() is True
    refresh.assert_not_called()
    assert data_updater_ui.has_pending_background_catalog_refresh() is True
    data_updater_ui._background_catalog_refresh_pending = False


def test_run_background_catalog_update_keeps_cache_after_required_failure(tmp_path, mocker):
    from ui import data_updater_ui

    data_updater_ui._background_catalog_refresh_pending = False
    required = _repo(tmp_path, "cards", required=True, cached=False)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required])
    mocker.patch("ui.data_updater_ui.utils.update_data_repo", return_value=False)
    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")

    assert data_updater_ui._run_background_catalog_update() is False
    refresh.assert_not_called()
    assert data_updater_ui.has_pending_background_catalog_refresh() is False


def test_run_background_catalog_update_handles_update_exception(tmp_path, mocker):
    from ui import data_updater_ui

    data_updater_ui._background_catalog_refresh_pending = False
    required = _repo(tmp_path, "cards", required=True, cached=False)
    mocker.patch.object(data_updater_ui.variables, "DATA_REPOSITORIES", [required])
    mocker.patch("ui.data_updater_ui.utils.update_data_repo", side_effect=RuntimeError("offline"))
    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")

    assert data_updater_ui._run_background_catalog_update() is False
    refresh.assert_not_called()
    assert data_updater_ui.has_pending_background_catalog_refresh() is False


def test_apply_pending_background_catalog_refresh_is_silent_and_one_shot(mocker):
    from ui import data_updater_ui

    refresh = mocker.patch("ui.data_updater_ui._refresh_loaded_catalog_data")
    data_updater_ui._background_catalog_refresh_pending = False

    assert data_updater_ui.apply_pending_background_catalog_refresh() is False
    refresh.assert_not_called()

    data_updater_ui.mark_background_catalog_refresh_pending()
    assert data_updater_ui.has_pending_background_catalog_refresh() is True
    assert data_updater_ui.apply_pending_background_catalog_refresh() is True
    refresh.assert_called_once()
    assert data_updater_ui.has_pending_background_catalog_refresh() is False


def test_start_background_catalog_update_starts_only_once(mocker):
    from ui import data_updater_ui

    data_updater_ui._background_update_thread = None
    data_updater_ui._background_update_stop.clear()

    class FakeThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

        def is_alive(self):
            return self.started

    thread_class = mocker.patch("ui.data_updater_ui.threading.Thread", side_effect=FakeThread)

    first = data_updater_ui.start_background_catalog_update(interval_seconds=1, run_immediately=True)
    second = data_updater_ui.start_background_catalog_update(interval_seconds=2)

    assert first is second
    assert first.args == (1, True)
    assert first.daemon is True
    assert thread_class.call_count == 1
    data_updater_ui._background_update_thread = None


def test_stop_background_catalog_update_sets_event_and_joins_live_thread(mocker):
    from ui import data_updater_ui

    thread = MagicMock()
    thread.is_alive.return_value = True
    data_updater_ui._background_update_thread = thread

    data_updater_ui.stop_background_catalog_update(timeout=3)

    assert data_updater_ui._background_update_stop.is_set()
    thread.join.assert_called_once_with(3)
    data_updater_ui._background_update_stop.clear()
    data_updater_ui._background_update_thread = None


def test_background_update_loop_can_run_immediately_and_on_interval(mocker):
    from ui import data_updater_ui

    update = mocker.patch("ui.data_updater_ui._run_background_catalog_update")
    mocker.patch.object(data_updater_ui._background_update_stop, "wait", side_effect=[False, True])

    data_updater_ui._background_update_loop(5, run_immediately=True)

    assert update.call_count == 2
