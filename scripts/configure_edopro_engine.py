"""Copy a prebuilt EDOPro/ocgcore engine and scripts into bundled locations.

Usage:
    python scripts/configure_edopro_engine.py --ocgcore C:\path\ocgcore.dll
    python scripts/configure_edopro_engine.py --ocgcore C:\path\ocgcore.dll --scripts C:\path\CardScripts\script
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CORE_DIR = ROOT / "src" / "data" / "core"
SCRIPT_DIR = ROOT / "src" / "data" / "scripts"


def main() -> int:
    parser = argparse.ArgumentParser(description="Bundle EDOPro engine assets into this project")
    parser.add_argument("--ocgcore", required=True, help="Path to ocgcore shared library")
    parser.add_argument("--scripts", help="Path to EDOPro card script directory")
    args = parser.parse_args()

    ocgcore = Path(args.ocgcore)
    if not ocgcore.is_file():
        print(f"ERROR: ocgcore not found: {ocgcore}", file=sys.stderr)
        return 1

    CORE_DIR.mkdir(parents=True, exist_ok=True)
    target = CORE_DIR / ocgcore.name
    shutil.copy2(ocgcore, target)
    print(f"Bundled engine: {target}")

    if args.scripts:
        scripts = Path(args.scripts)
        if not scripts.is_dir():
            print(f"ERROR: script directory not found: {scripts}", file=sys.stderr)
            return 1
        if SCRIPT_DIR.exists():
            shutil.rmtree(SCRIPT_DIR)
        shutil.copytree(scripts, SCRIPT_DIR)
        print(f"Bundled scripts: {SCRIPT_DIR}")

    print("Done. Local (Offline) will use the bundled EDOPro engine automatically.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
