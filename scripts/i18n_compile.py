"""Compile .po files into .mo binary files for runtime use.

Usage:
    python scripts/i18n_compile.py

Requires: babel (pip install babel)
"""

import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOCALE_DIR = ROOT / "locales"
DOMAIN = "yugiohaccess"


def pybabel_cmd():
    found = shutil.which("pybabel")
    if found:
        return [found]
    suffix = ".exe" if sys.platform == "win32" else ""
    local = ROOT / ".venv" / "Scripts" / f"pybabel{suffix}"
    if local.exists():
        return [str(local)]
    return [sys.executable, "-m", "babel.messages.frontend"]


def main():
    po_files = list(LOCALE_DIR.rglob(f"{DOMAIN}.po"))
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

    for po in po_files:
        mo = po.with_suffix(".mo")
        if mo.exists():
            print(f"  {mo.relative_to(ROOT)} ({mo.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"  WARNING: {mo.relative_to(ROOT)} not generated")

    print("Done.")


if __name__ == "__main__":
    main()
