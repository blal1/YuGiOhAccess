"""The translation catalogues have to match the source and mean something.

Three ways this quietly broke before:

* the template drifted from the source, so strings added months earlier were
  invisible to translators and could never be translated;
* seven catalogues with nothing in them shipped anyway, which put seven
  languages in the settings menu that changed nothing when chosen;
* sentences were assembled from English fragments, so they stayed in English
  even where a translation existed.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
LOCALES = ROOT / "locales"
POT = LOCALES / "yugiohaccess.pot"
DOMAIN = "yugiohaccess"

pytest.importorskip("babel")


def _message_ids(po_path):
    """Every message id in a catalogue, with plurals flattened.

    A plural message is keyed by a ``(singular, plural)`` tuple, so a set of
    raw ids does not contain either form on its own.
    """
    from babel.messages.pofile import read_po

    with po_path.open("rb") as handle:
        catalogue = read_po(handle)
    ids = set()
    for message in catalogue:
        if not message.id:
            continue
        if isinstance(message.id, (list, tuple)):
            ids.update(message.id)
        else:
            ids.add(message.id)
    return ids


def _extract_to(target):
    """Run the same extraction the i18n_extract script runs."""
    sys.path.insert(0, str(ROOT))
    from scripts.i18n_extract import pybabel_cmd

    result = subprocess.run(
        [
            *pybabel_cmd(), "extract",
            "-F", str(ROOT / "babel.cfg"),
            "-o", str(target),
            "-k", "_", "-k", "N_",
            "-k", "ngettext:1,2",
            "-k", "pgettext:1c,2",
            "src/",
        ],
        cwd=str(ROOT),
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return target


def test_the_template_matches_the_source(tmp_path):
    """Every translatable string in the source is in the template.

    The committed template had fallen sixteen strings behind, so anything
    added after it was last generated -- the duel history screen among them --
    could not be translated at all.
    """
    if shutil.which("git") is None and not POT.exists():
        pytest.skip("no template to compare against")

    fresh = _extract_to(tmp_path / "fresh.pot")
    missing = _message_ids(fresh) - _message_ids(POT)

    assert not missing, (
        f"{len(missing)} string(s) in the source are not in {POT.name}. "
        f"Run scripts/i18n_extract.py. First few: {sorted(str(m) for m in missing)[:5]}"
    )


@pytest.mark.parametrize(
    "mo_file", sorted(LOCALES.rglob(f"{DOMAIN}.mo")), ids=lambda p: p.parent.parent.name
)
def test_every_shipped_catalogue_actually_translates_something(mo_file):
    from core import i18n

    assert i18n.catalogue_is_translated(mo_file), (
        f"{mo_file.relative_to(ROOT)} holds no translations. Shipping it puts "
        f"the language in the settings menu and then changes nothing when the "
        f"player picks it."
    )


def test_offered_languages_all_have_a_name():
    """A language the player is offered is named, not shown as a bare code."""
    from core import i18n

    for code in i18n.get_available_languages():
        assert code in i18n.SUPPORTED_LANGUAGES, (
            f"{code!r} is offered but has no display name in SUPPORTED_LANGUAGES"
        )


def test_named_languages_are_not_promises():
    """The name table is allowed to be ahead of the translations, not behind.

    It used to list Turkish and Russian, for which nothing existed at all.
    Names are fine to keep; what matters is that the menu is driven by the
    catalogues on disk rather than by this table.
    """
    from core import i18n

    offered = set(i18n.get_available_languages())
    assert offered <= set(i18n.SUPPORTED_LANGUAGES) | {"en"}


def test_a_packaged_build_can_find_its_translations(mocker, tmp_path):
    """Frozen, the catalogues sit beside the executable, not up two directories.

    Resolving them from this module's own path put them outside the bundle,
    so every release was English only whatever had been translated.
    """
    from core import i18n

    mocker.patch.object(i18n.variables, "IS_FROZEN", True)
    mocker.patch.object(i18n.variables, "EXECUTABLE_DIR", tmp_path)
    assert i18n._default_locale_dir() == tmp_path / "locales"

    mocker.patch.object(i18n.variables, "IS_FROZEN", False)
    assert i18n._default_locale_dir() == ROOT / "locales"


def test_the_packaging_spec_ships_the_translations():
    """Asserted against the spec's actual output, not its source text.

    Matching a literal line broke the moment the spec was rewritten, while
    saying nothing about whether the translations were still bundled.
    """
    import sys

    sys.path.insert(0, str(ROOT / "specs"))
    import common

    destinations = {destination for _source, destination in common.datas}
    assert "locales" in destinations, (
        "the packaging spec does not bundle the locales directory, so a "
        "packaged build has no translations to load"
    )


@pytest.mark.parametrize("sentence", [
    "You prepare to attack directly with {card}.",
    "Your opponent prepares to attack directly with {card}.",
    "You prepare to attack {target} with {card}.",
    "Your opponent prepares to attack {target} with {card}.",
    "You are summoning {card} ({stats}) in {position} position.",
    "Your opponent is summoning {card} ({stats}) in {position} position.",
    "You are special summoning {card} ({stats}) in {position} position.",
    "Your opponent is special summoning {card} ({stats}) in {position} position.",
    "You show your opponent {count} card.",
    "Your opponent shows you {count} card.",
])
def test_duel_announcements_are_whole_sentences(sentence):
    """Each announcement is one translatable unit, not a subject plus a tail.

    These were built by substituting a hardcoded "You" or "Your opponent" into
    a shared sentence. The subject never reached a translator, and no language
    that inflects the verb after it could have been translated that way.
    """
    assert sentence in _message_ids(POT), (
        f"{sentence!r} is not in the template; regenerate it with "
        f"scripts/i18n_extract.py"
    )


@pytest.mark.parametrize("special", [False, True])
@pytest.mark.parametrize("mine", [False, True])
@pytest.mark.parametrize("link", [False, True])
def test_every_summon_announcement_formats(mocker, special, mine, link):
    """All four sentences, with and without a defense to read out.

    A sentence built by ``.format`` fails at the moment it is spoken if a
    placeholder is misspelled, so each combination is worth running once.
    """
    from game.card import card_constants
    from ui.duel_messages import summoning

    output = mocker.patch("ui.duel_messages.summoning.utils.output")
    client = mocker.MagicMock()
    client.what_player_am_i = 0

    card = mocker.MagicMock()
    card.controller = 0 if mine else 1
    card.type = card_constants.TYPE.LINK if link else card_constants.TYPE.MONSTER
    card.attack = 1500
    card.defense = 1200
    card.get_name.return_value = "Test Monster"
    card.get_position.return_value = "face-up attack"

    summoning.summoning(
        client, card, card.controller, card_constants.LOCATION.MONSTER_ZONE, 0,
        card_constants.POSITION.FACE_UP_ATTACK, special=special,
    )

    spoken = output.call_args.args[0]
    assert "Test Monster" in spoken
    assert "face-up attack" in spoken
    assert ("1500" if link else "1500/1200") in spoken
    assert "{" not in spoken, f"a placeholder was left unfilled: {spoken}"
