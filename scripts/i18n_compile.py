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
