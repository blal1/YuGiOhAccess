"""Generate the bot deck catalogue from WindBot's own executor attributes.

Every WindBot executor declares ``[Deck("Key", "AI_File")]``. ``Key`` is what
``DecksManager.Instantiate`` looks up and what ``bots.json`` stores; ``AI_File``
is the deck file on disk. The two differ often enough that guessing is wrong:
``Level VIII`` lives in ``AI_Level8.ydk``, ``Blue-Eyes`` in ``AI_BlueEyes.ydk``.

``src/bot/launcher.py`` used to carry a hand written map of four decks and fall
back to stripping the ``AI_`` prefix, which silently mislabels most of the
catalogue; a key that does not resolve makes WindBot pick a random deck instead
of the one the player chose.

Usage:
    python scripts/generate_bot_decks.py [--check]
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
EXECUTOR_DIR = ROOT / "Game" / "AI" / "Decks"
DECK_DIR = ROOT / "Decks"
OUTPUT = ROOT / "src" / "bot" / "deck_catalogue.py"

DECK_ATTRIBUTE = re.compile(
    r'\[Deck\(\s*"([^"]+)"\s*,\s*"([^"]+)"(?:\s*,\s*"([^"]+)")?\s*\)\]'
)

HEADER = '''"""Bot decks this build can actually pilot.

DO NOT EDIT BY HAND. Regenerate with::

    python scripts/generate_bot_decks.py

Generated from the ``[Deck(...)]`` attributes of the bundled WindBot executors,
cross checked against the deck files in ``Decks/``. An executor without its deck
file, or a deck file without an executor, is left out: WindBot would fall back
to a random deck and the player would get something they did not choose.
"""

# WindBot deck key -> deck file stem in Decks/
KEY_TO_DECK_FILE: dict[str, str] = {
'''


def parse_executors(executor_dir: Path) -> dict[str, tuple[str, str]]:
    """Read every ``[Deck]`` attribute: key -> (deck file stem, difficulty level)."""
    catalogue: dict[str, tuple[str, str]] = {}
    for path in sorted(executor_dir.glob("*.cs")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in DECK_ATTRIBUTE.finditer(text):
            key, deck_file, level = match.group(1), match.group(2), match.group(3) or "Normal"
            if key in catalogue and catalogue[key][0] != deck_file:
                raise SystemExit(f"{key} is declared twice with different deck files")
            catalogue[key] = (deck_file, level)
    if not catalogue:
        raise SystemExit(f"No [Deck(...)] attributes found in {executor_dir}")
    return catalogue


def playable(catalogue: dict[str, tuple[str, str]], deck_dir: Path) -> dict[str, tuple[str, str]]:
    return {
        key: value for key, value in catalogue.items()
        if (deck_dir / f"{value[0]}.ydk").exists()
    }


def render(catalogue: dict[str, tuple[str, str]]) -> str:
    lines = [HEADER]
    for key, (deck_file, _level) in sorted(catalogue.items()):
        lines.append(f"    {key!r}: {deck_file!r},\n")
    lines.append("}\n\n")
    lines.append("# Difficulty as the executor declares it: Easy, Normal or NotFinished.\n")
    lines.append("KEY_TO_LEVEL: dict[str, str] = {\n")
    for key, (_deck_file, level) in sorted(catalogue.items()):
        lines.append(f"    {key!r}: {level!r},\n")
    lines.append("}\n\n")
    lines.append("DECK_FILE_TO_KEY: dict[str, str] = {\n")
    for key, (deck_file, _level) in sorted(catalogue.items(), key=lambda item: item[1][0]):
        lines.append(f"    {deck_file!r}: {key!r},\n")
    lines.append("}\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in module is stale.")
    parser.add_argument("--executors", type=Path, default=EXECUTOR_DIR)
    parser.add_argument("--decks", type=Path, default=DECK_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()

    if not args.executors.exists():
        print(f"No WindBot executors at {args.executors}", file=sys.stderr)
        return 2

    everything = parse_executors(args.executors)
    catalogue = playable(everything, args.decks)
    skipped = sorted(set(everything) - set(catalogue))
    if skipped:
        print(f"Skipping {len(skipped)} executor(s) with no deck file: {', '.join(skipped)}")

    rendered = render(catalogue)
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            print(f"{args.output} is out of date; run scripts/generate_bot_decks.py", file=sys.stderr)
            return 1
        print(f"{args.output} is up to date ({len(catalogue)} decks).")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output} with {len(catalogue)} playable decks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
