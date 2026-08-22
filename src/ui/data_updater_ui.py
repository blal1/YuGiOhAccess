import logging
import threading
import concurrent.futures

import wx
from core import utils
from core import variables
from core.i18n import _

from ui.base_ui import VerticalMenu
from ui import main_ui

logger = logging.getLogger(__name__)
RESULT_UI = main_ui.first_ui
BACKGROUND_UPDATE_INTERVAL_SECONDS = 30 * 60
_background_update_thread = None
_background_update_stop = threading.Event()
_background_update_lock = threading.Lock()
_catalog_refresh_lock = threading.Lock()
_background_catalog_refresh_pending = False

@utils.ui_function
def ensure_yugioh_data_is_up_to_date():
    logger.info("Ensuring YuGiOh data is up to date")
    updater_menu = VerticalMenu(_("Loading data"))
    updater_menu.append_item(_("Loading data, please wait..."), None)
    threading.Thread(target=_update_data_thread, daemon=True).start()
    return updater_menu

def _has_cached_data():
    """Check if usable cached data exists from a previous sync."""
    for repo in variables.DATA_REPOSITORIES:
        if not repo.get("required", True):
            continue
        path = repo["local_path"]
        if not path.exists() or not any(path.iterdir()):
            return False
    return True


def _refresh_loaded_catalog_data():
    """Reconnect card databases/translations and reload banlists after a sync."""
    with _catalog_refresh_lock:
        handler = variables.LANGUAGE_HANDLER
        if handler:
            handler.add_available_languages()
            handler.connect_all_databases()
            language = variables.config.get("language", "english")
            if not handler.is_loaded(language):
                language = "english"
                variables.config.set("language", language)
            if handler.is_loaded(language):
                handler.set_primary_language(language)
        from game.edo import banlists
        banlists.BanlistManager().reload()


def has_pending_background_catalog_refresh():
    return _background_catalog_refresh_pending


def mark_background_catalog_refresh_pending():
    global _background_catalog_refresh_pending
    _background_catalog_refresh_pending = True


def apply_pending_background_catalog_refresh():
    """Apply a downloaded background update without changing the active UI."""
    global _background_catalog_refresh_pending
    if not _background_catalog_refresh_pending:
        return False
    _refresh_loaded_catalog_data()
    _background_catalog_refresh_pending = False
    logger.info("Pending background catalog refresh applied")
    return True


def _required_updates_succeeded(results):
    return all(result for repo, result in results if repo.get("required", True))


def _update_data_thread():
    logger.info("Starting data update thread")
    all_has_executed = False
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(utils.update_data_repo, **repo): repo for repo in variables.DATA_REPOSITORIES}
        while not all_has_executed:
            wx.Yield()
            for future in concurrent.futures.as_completed(futures):
                repo = futures[future]
                try:
                    results.append((repo, future.result()))
                except Exception as e:
                    logger.error(f"Failed to update: {e}")
                    results.append((repo, False))
                    break
            if all(future.done() for future in futures):
                all_has_executed = True
                break
        if _required_updates_succeeded(results):
            logger.info("All data updates successful")
            _refresh_loaded_catalog_data()
            start_background_catalog_update()
            wx.CallAfter(RESULT_UI)
        else:
            logger.error("Data update failed")
            if _has_cached_data():
                logger.info("Using cached data from previous sync")
                _refresh_loaded_catalog_data()
                start_background_catalog_update()
                wx.CallAfter(_warn_cached_then_continue)
            else:
                wx.CallAfter(failed_data_update)


def start_background_catalog_update(interval_seconds=BACKGROUND_UPDATE_INTERVAL_SECONDS, run_immediately=False):
    """Start a daemon updater for card databases, translations and banlists."""
    global _background_update_thread
    with _background_update_lock:
        if _background_update_thread and _background_update_thread.is_alive():
            return _background_update_thread
        _background_update_stop.clear()
        _background_update_thread = threading.Thread(
            target=_background_update_loop,
            args=(interval_seconds, run_immediately),
            daemon=True,
        )
        _background_update_thread.start()
        return _background_update_thread


def stop_background_catalog_update(timeout=1):
    _background_update_stop.set()
    thread = _background_update_thread
    if thread and thread.is_alive():
        thread.join(timeout)


def _background_update_loop(interval_seconds, run_immediately=False):
    if run_immediately:
        _run_background_catalog_update()
    while not _background_update_stop.wait(interval_seconds):
        _run_background_catalog_update()


def _run_background_catalog_update():
    logger.info("Checking for card catalog, translation and banlist updates")
    results = []
    for repo in variables.DATA_REPOSITORIES:
        try:
            results.append((repo, utils.update_data_repo(**repo)))
        except Exception as e:
            logger.error("Failed to update %s in background: %s", repo.get("name", "data"), e)
            results.append((repo, False))
    if _required_updates_succeeded(results):
        mark_background_catalog_refresh_pending()
        logger.info("Card catalog, translation and banlist downloads completed in background")
        return True
    logger.warning("Background data update failed; keeping existing cached catalog data")
    return False

@utils.ui_function
def _warn_cached_then_continue():
    utils.output(_("Could not update card data. Using cached data which may be outdated."))
    RESULT_UI()


@utils.ui_function
def failed_data_update():
    logger.error("Data update failed")
    fail_menu = VerticalMenu(_("Data update failed"))
    fail_menu.append_item(_("Data update failed. Please check your internet connection and try again."), None)
    fail_menu.append_item(_("Retry"), ensure_yugioh_data_is_up_to_date)
    fail_menu.append_item(_("Exit"), wx.GetTopLevelWindows()[0].Close)
    return fail_menu
