"""Copy the bot's data files into the directory WindBot actually reads.

WindBot loads decks from ``Program.AssetPath/Decks`` (see Game/AI/Deck.cs), which
is the published output under ``src/data/bot`` and not the repository root. The
csproj copies these files, so a full ``dotnet publish`` keeps them in step, but
the two drift apart as soon as a deck is added without rebuilding, and rebuilding
needs the .NET SDK.

When they drift the failure is silent and confusing: the deck menu offers a deck,
WindBot cannot find the file, never sends its deck to the server, and the room
reports "waiting for every player deck to be loaded".

Usage:
    python scripts/sync_bot_assets.py [--check]
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ASSET_DIR = ROOT / "src" / "data" / "bot"

# (source, destination relative to the asset directory, glob or None for a file)
ASSETS = [
    (ROOT / "Decks", "Decks", "*.ydk"),
    (ROOT / "Dialogs", "Dialogs", "*.json"),
    (ROOT / "bots.json", "bots.json", None),
]


def _files_to_copy(asset_dir: Path):
    """Yield (source, destination) for everything that is missing or stale."""
    for source, destination, pattern in ASSETS:
        if pattern is None:
            if not source.exists():
                continue
            target = asset_dir / destination
            if not target.exists() or not filecmp.cmp(source, target, shallow=False):
                yield source, target
            continue
        if not source.is_dir():
            continue
        for path in sorted(source.glob(pattern)):
            target = asset_dir / destination / path.name
            if not target.exists() or not filecmp.cmp(path, target, shallow=False):
                yield path, target


def sync(asset_dir: Path = ASSET_DIR, check: bool = False) -> int:
    if not asset_dir.exists():
        print(
            f"{asset_dir} does not exist. Run scripts/build_windbot.py first.",
            file=sys.stderr,
        )
        return 2

    pending = list(_files_to_copy(asset_dir))
    if check:
        if pending:
            print(f"{len(pending)} bot asset(s) are out of date:", file=sys.stderr)
            for source, _target in pending:
                print(f"  {source.relative_to(ROOT)}", file=sys.stderr)
            print("Run python scripts/sync_bot_assets.py", file=sys.stderr)
            return 1
        print("Bot assets are up to date.")
        return 0

    for source, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    print(f"Synchronised {len(pending)} bot asset(s) into {asset_dir}")
    decks = len(list((asset_dir / "Decks").glob("*.ydk"))) if (asset_dir / "Decks").exists() else 0
    print(f"{decks} deck(s) are now available to the bot")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report drift instead of copying.")
    parser.add_argument("--asset-dir", type=Path, default=ASSET_DIR)
    args = parser.parse_args()
    return sync(args.asset_dir, args.check)


if __name__ == "__main__":
    raise SystemExit(main())
