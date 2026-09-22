"""What actually goes into a packaged build.

The spec used to hand PyInstaller the whole of src/data, which swept in a
34 MB copy of the bot's published output that nothing reads, the downloaded
card database archive, and debug symbols. Nobody noticed because nothing
looked.
"""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "specs"))


@pytest.fixture(scope="module")
def spec():
    import common

    return common


def _sources(spec):
    return [source.replace(os.sep, "/") for source, _destination in spec.datas]


def test_the_runtime_assets_are_bundled(spec):
    """Sounds, card scripts, the engine, the card strings and the decks."""
    destinations = {destination for _source, destination in spec.datas}
    for required in ("data/sounds", "data/scripts", "data/core", "data/locales", "data/decks"):
        assert required in destinations, f"{required} is missing from the build"


def test_the_bot_and_databases_are_bundled(spec):
    destinations = {destination for _source, destination in spec.datas}
    assert any(d.startswith("data/bot") for d in destinations), "the bot is missing from the build"
    assert any(d.startswith("data/databases") for d in destinations), "the card databases are missing"


@pytest.mark.parametrize("unwanted", [
    "bot-publish-test",  # a copy of the bot's output that nothing reads
    "babelcdb.zip",      # the downloaded archive, re-fetched at startup anyway
    "BabelCDB-master",   # and its extraction
])
def test_build_leftovers_are_not_bundled(spec, unwanted):
    assert not any(unwanted in source for source in _sources(spec)), (
        f"{unwanted} is still being bundled into every build"
    )


def test_debug_symbols_are_not_bundled(spec):
    assert not any(source.endswith(".pdb") for source in _sources(spec))


def test_the_translations_are_bundled(spec):
    destinations = {destination for _source, destination in spec.datas}
    assert "locales" in destinations


def test_every_bundled_source_exists(spec):
    """A path that does not exist fails the build late and confusingly."""
    missing = [source for source, _destination in spec.datas if not os.path.exists(source)]
    assert not missing, f"the spec points at files that are not there: {missing[:3]}"


def test_the_filter_keeps_directories_out_by_name(spec):
    assert spec._should_bundle("bot-publish-test", True) is False
    assert spec._should_bundle("__pycache__", True) is False
    assert spec._should_bundle("Decks", True) is True


def test_the_filter_keeps_generated_files_out(spec):
    assert spec._should_bundle("babelcdb.zip", False) is False
    assert spec._should_bundle("WindBot.Desktop.pdb", False) is False
    assert spec._should_bundle("WindBot.Desktop.dll", False) is True
