from pathlib import Path
from unittest.mock import MagicMock, patch


def test_has_cached_data_all_present(mocker, tmp_path):
    """Returns True when all repos have non-empty local paths."""
    repo1_path = tmp_path / "repo1"
    repo1_path.mkdir()
    (repo1_path / "cards.cdb").write_text("data")
    repo2_path = tmp_path / "repo2"
    repo2_path.mkdir()
    (repo2_path / "script.lua").write_text("data")

    mocker.patch("core.variables.DATA_REPOSITORIES", [
        {"local_path": repo1_path},
        {"local_path": repo2_path},
    ])

    from ui.data_updater_ui import _has_cached_data
    assert _has_cached_data() is True


def test_has_cached_data_missing_dir(mocker, tmp_path):
    """Returns False when a repo path doesn't exist."""
    mocker.patch("core.variables.DATA_REPOSITORIES", [
        {"local_path": tmp_path / "nonexistent"},
    ])

    from ui.data_updater_ui import _has_cached_data
    assert _has_cached_data() is False


def test_has_cached_data_empty_dir(mocker, tmp_path):
    """Returns False when a repo path is empty."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    mocker.patch("core.variables.DATA_REPOSITORIES", [
        {"local_path": empty_dir},
    ])

    from ui.data_updater_ui import _has_cached_data
    assert _has_cached_data() is False
