"""Extract translatable strings from source code into .pot template.

Usage:
    python scripts/i18n_extract.py

Requires: babel (pip install babel)

Generates: locales/yugiohaccess.pot (template for translators)
Updates existing .po files with new strings.
"""

import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOCALE_DIR = ROOT / "locales"
POT_FILE = LOCALE_DIR / "yugiohaccess.pot"
DOMAIN = "yugiohaccess"
BABEL_CFG = ROOT / "babel.cfg"


def pybabel_cmd():
    found = shutil.which("pybabel")
    if found:
        return [found]
    suffix = ".exe" if sys.platform == "win32" else ""
    local = ROOT / ".venv" / "Scripts" / f"pybabel{suffix}"
    if local.exists():
        return [str(local)]
    return [sys.executable, "-m", "babel.messages.frontend"]


def run(cmd):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    LOCALE_DIR.mkdir(exist_ok=True)

    # Extract strings into .pot template
    print("Extracting strings...")
    pybabel = pybabel_cmd()
    run([
        *pybabel, "extract",
        "-F", str(BABEL_CFG),
        "-o", str(POT_FILE),
        "--project", "YuGiOhAccess",
        "--version", "1.0",
        "--copyright-holder", "YuGiOhAccess Contributors",
        "--msgid-bugs-address", "translations@yugiohaccess.com",
        "-k", "_",
        "-k", "ngettext:1,2",
        "-k", "pgettext:1c,2",
        "src/",
    ])
    print(f"Template: {POT_FILE}")

    # Update existing .po files
    for lang_dir in LOCALE_DIR.iterdir():
        if not lang_dir.is_dir() or lang_dir.name.startswith("."):
            continue
        po_file = lang_dir / "LC_MESSAGES" / f"{DOMAIN}.po"
        if po_file.exists():
            print(f"Updating {po_file.relative_to(ROOT)}...")
            run([
                *pybabel, "update",
                "-i", str(POT_FILE),
                "-d", str(LOCALE_DIR),
                "-D", DOMAIN,
                "-l", lang_dir.name,
            ])
        else:
            print(f"Initializing {lang_dir.name}...")
            po_file.parent.mkdir(parents=True, exist_ok=True)
            run([
                *pybabel, "init",
                "-i", str(POT_FILE),
                "-d", str(LOCALE_DIR),
                "-D", DOMAIN,
                "-l", lang_dir.name,
            ])

    print("\nDone. Translate .po files, then run: python scripts/i18n_compile.py")


if __name__ == "__main__":
    main()
