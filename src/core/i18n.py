"""Internationalization support using gettext + Babel.

UI strings use gettext .mo files compiled from .po translations.
Card names use the separate CDB database system (language_handler.py).

Usage in any module:
    from core.i18n import _
    utils.output(_("Bot added to room"))

For strings with variables:
    utils.output(_("Changed nickname to {name}").format(name=new_nickname))
"""

import gettext
import logging
from pathlib import Path

from core import variables

logger = logging.getLogger(__name__)

_DOMAIN = "yugiohaccess"
_current_translation: gettext.GNUTranslations | gettext.NullTranslations = gettext.NullTranslations()


def _default_locale_dir() -> Path:
    """Where the compiled catalogues live.

    In a packaged build everything is unpacked beside the executable, so the
    path from this module's own location lands outside the bundle entirely.
    That made the UI English-only in every release, however complete the
    translations were.
    """
    if getattr(variables, "IS_FROZEN", False):
        return Path(variables.EXECUTABLE_DIR) / "locales"
    return Path(__file__).parent.parent.parent / "locales"


_locale_dir: Path = _default_locale_dir()

# What to call each language, in that language. This is a naming table, not a
# statement that a translation exists: what the player is offered comes from
# the catalogues actually on disk. A language listed here with nothing behind
# it is simply never shown, and a language on disk with no entry here is shown
# under its own code.
SUPPORTED_LANGUAGES = {
    "en": "English",
    "fr": "Français",
    "es": "Español",
    "de": "Deutsch",
    "it": "Italiano",
    "pt": "Português",
    "ja": "日本語",
    "zh": "中文",
    "ko": "한국어",
    "ar": "العربية",
}


def get_locale_dir() -> Path:
    return _locale_dir


def catalogue_is_translated(mo_file: Path) -> bool:
    """Whether a compiled catalogue holds any translation at all.

    A .po file with every entry left blank still compiles to a valid .mo; it
    just contains nothing but its own header. Seven of those shipped, and each
    one put a language in the settings menu that changed absolutely nothing
    when the player picked it.
    """
    try:
        with open(mo_file, "rb") as handle:
            catalogue = gettext.GNUTranslations(handle)
    except Exception:
        # Anything at all: unreadable, truncated, not a catalogue. A broken
        # file on disk must not take the settings menu down with it, and a
        # language whose catalogue will not load is one we cannot offer.
        logger.warning("Could not read the translation catalogue %s", mo_file, exc_info=True)
        return False
    # Every catalogue carries one entry for its own metadata header, keyed by
    # the empty string. Anything beyond that is a real translation.
    return any(key for key in catalogue._catalog)  # type: ignore[attr-defined]


def get_available_languages() -> dict[str, str]:
    """Language code -> display name, for languages the player can actually use.

    Only catalogues that contain translations are offered. Listing one that is
    empty is worse than not offering the language at all: the player chooses
    it, is told the language changed, and every word stays in English.
    """
    available = {"en": "English"}
    if not _locale_dir.exists():
        return available
    for lang_dir in sorted(_locale_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        mo_file = lang_dir / "LC_MESSAGES" / f"{_DOMAIN}.mo"
        if not mo_file.exists() or not catalogue_is_translated(mo_file):
            continue
        code = lang_dir.name
        available[code] = SUPPORTED_LANGUAGES.get(code, code)
    return available


def setup(lang_code: str = ""):
    """Initialize or switch the UI translation.

    Call at startup and when the user changes their UI language preference.
    """
    global _current_translation

    if not lang_code:
        lang_code = variables.config.get("ui_language", "en")

    if lang_code == "en":
        _current_translation = gettext.NullTranslations()
        logger.info("UI language set to English (no translation)")
        return

    if lang_code not in get_available_languages():
        # A language saved in the config before its translation was withdrawn,
        # or one that was only ever an empty catalogue. Say so once rather
        # than claiming to have switched to it.
        logger.warning("No usable translation for '%s', falling back to English", lang_code)
        _current_translation = gettext.NullTranslations()
        return

    locale_path = str(_locale_dir)
    try:
        _current_translation = gettext.translation(
            _DOMAIN, localedir=locale_path, languages=[lang_code]
        )
        logger.info("UI language set to %s", lang_code)
    except FileNotFoundError:
        logger.warning("Translation not found for '%s', falling back to English", lang_code)
        _current_translation = gettext.NullTranslations()


def _(message: str) -> str:
    """Translate a UI string. This is the primary translation function."""
    return _current_translation.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Translate with plural forms."""
    return _current_translation.ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """Translate with context disambiguation."""
    return _current_translation.pgettext(context, message)

def N_(message: str) -> str:
    """Mark a string for extraction without translating it yet.

    Use for strings defined at import time (module-level tables); translate the
    value with ``_()`` at the point of use, after ``setup()`` has run.
    """
    return message
