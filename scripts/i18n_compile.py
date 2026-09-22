"""Compile .po files into .mo binary files for runtime use.

Usage:
    python scripts/i18n_compile.py

Requires: babel (pip install babel)
"""


import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Support both `python scripts/i18n_compile.py` (as the usage line above and
# i18n_extract.py's closing message both say) and `python -m scripts.i18n_compile`.
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from scripts.i18n_extract import pybabel_cmd  # noqa: E402
LOCALE_DIR = ROOT / "locales"
DOMAIN = "yugiohaccess"

__all__ = ["pybabel_cmd", "main"]


def translation_counts(po_file):
    """How many messages a .po file defines, and how many are usable.

    Parsed with Babel rather than by pattern: a long translation is written as
    an empty ``msgstr`` followed by continuation lines, and a plural has
    ``msgstr[0]``, so counting raw lines gets both of them backwards.

    Fuzzy entries count as untranslated, because that is what they are at
    runtime: the compiler leaves them out unless asked for them.
    """
    from babel.messages.pofile import read_po

    with po_file.open("rb") as handle:
        catalogue = read_po(handle)

    total = 0
    translated = 0
    for message in catalogue:
        if not message.id:
            continue  # the catalogue header, which is not a message
        total += 1
        if message.fuzzy:
            continue
        string = message.string
        if isinstance(string, (list, tuple)):
            if any(string):
                translated += 1
        elif string:
            translated += 1
    return total, translated


def main():
    po_files = sorted(LOCALE_DIR.rglob(f"{DOMAIN}.po"))
    if not po_files:
        print("No .po files found. Run scripts/i18n_extract.py first.")
        sys.exit(1)

    print(f"Compiling {len(po_files)} translation file(s)...")
    result = subprocess.run(
        [*pybabel_cmd(), "compile", "-d", str(LOCALE_DIR), "-D", DOMAIN],
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        print("Compilation failed.", file=sys.stderr)
        sys.exit(1)

    empty = []
    for po in po_files:
        language = po.parent.parent.name
        total, translated = translation_counts(po)
        mo = po.with_suffix(".mo")
        if translated == 0:
            # A .po with nothing filled in still compiles, to a catalogue that
            # holds only its own header. Shipping that puts the language in the
            # settings menu and then changes nothing when it is chosen, which
            # is worse for the player than not offering it.
            mo.unlink(missing_ok=True)
            empty.append(language)
            print(f"  {language}: nothing translated yet, no catalogue written")
            continue
        if not mo.exists():
            print(f"  WARNING: {mo.relative_to(ROOT)} not generated")
            continue
        share = 100.0 * translated / total if total else 0.0
        print(f"  {language}: {translated}/{total} translated ({share:.0f}%), "
              f"{mo.relative_to(ROOT)} ({mo.stat().st_size / 1024:.1f} KB)")

    if empty:
        print("\nNot offered to players until someone translates them: "
              + ", ".join(sorted(empty)))
    print("Done.")


if __name__ == "__main__":
    main()
