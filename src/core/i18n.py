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
import locale
import logging
from pathlib import Path

from core import variables

logger = logging.getLogger(__name__)

_DOMAIN = "yugiohaccess"
_current_translation: gettext.GNUTranslations | gettext.NullTranslations = gettext.NullTranslations()
_locale_dir: Path = Path(__file__).parent.parent.parent / "locales"

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
    "tr": "Türkçe",
    "ru": "Русский",
}


def get_locale_dir() -> Path:
    return _locale_dir


def get_available_languages() -> dict[str, str]:
    """Return dict of language code → display name for languages that have .mo files."""
    available = {"en": "English"}
    if not _locale_dir.exists():
        return available
    for lang_dir in _locale_dir.iterdir():
        if not lang_dir.is_dir():
            continue
        mo_file = lang_dir / "LC_MESSAGES" / f"{_DOMAIN}.mo"
        if mo_file.exists():
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
