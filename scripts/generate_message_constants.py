"""Generate the duel message id table from ocgcore's ocgapi_constants.h.

The header lives in the (gitignored) ocgcore checkout produced by
``scripts/build_ocgcore.py``. The generated module is checked in so the client
still builds without that checkout; running this script refreshes it whenever
the core is rebuilt.

Usage:
    python scripts/generate_message_constants.py [--check]
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HEADER = ROOT / "build" / "ocgcore" / "source" / "ocgapi_constants.h"
OUTPUT = ROOT / "src" / "game" / "edo" / "message_constants.py"

DEFINE_RE = re.compile(r"^#define\s+(MSG_[A-Z0-9_]+)\s+(\d+)\s*$")

HEADER_COMMENT = '''"""Duel (game) message ids, generated from ocgcore's ocgapi_constants.h.

DO NOT EDIT BY HAND. Regenerate with::

    python scripts/generate_message_constants.py

This is the single source of truth for duel message ids. Client handlers
(``ui.duel_messages``) and the bundled server (``server.duel``) must both import
from here rather than re-declaring their own numbers.
"""

from enum import IntEnum


class MSG(IntEnum):
    """Duel message ids as defined by ocgcore."""

'''


def parse_header(header: Path) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    seen: dict[str, int] = {}
    for line in header.read_text(encoding="utf-8", errors="replace").splitlines():
        match = DEFINE_RE.match(line.strip())
        if not match:
            continue
        name, raw_value = match.group(1), int(match.group(2))
        if name in seen:
            if seen[name] != raw_value:
                raise SystemExit(f"Conflicting definitions for {name}: {seen[name]} and {raw_value}")
            continue
        seen[name] = raw_value
        entries.append((name, raw_value))
    if not entries:
        raise SystemExit(f"No MSG_* defines found in {header}")
    return entries


def render(entries: list[tuple[str, int]]) -> str:
    lines = [HEADER_COMMENT]
    by_value: dict[int, str] = {}
    for name, value in sorted(entries, key=lambda item: item[1]):
        if value in by_value:
            raise SystemExit(f"Duplicate message id {value}: {by_value[value]} and {name}")
        by_value[value] = name
        lines.append(f"    {name.removeprefix('MSG_')} = {value}\n")
    lines.append("\n\n")
    lines.append("# Module level aliases matching the C names, for readability at call sites.\n")
    for name, value in sorted(entries, key=lambda item: item[1]):
        lines.append(f"{name} = MSG.{name.removeprefix('MSG_')}\n")
    lines.append("\n")
    lines.append("MESSAGE_NAMES: dict[int, str] = {int(message): message.name for message in MSG}\n")
    lines.append("\n")
    lines.append("ALL_MESSAGE_IDS: frozenset[int] = frozenset(int(message) for message in MSG)\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the checked-in module is stale instead of rewriting it.",
    )
    parser.add_argument("--header", type=Path, default=HEADER, help="Path to ocgapi_constants.h")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="Path of the generated module")
    args = parser.parse_args()

    if not args.header.exists():
        print(
            f"ocgapi_constants.h not found at {args.header}.\n"
            "Run scripts/build_ocgcore.py first (it clones the core sources).",
            file=sys.stderr,
        )
        return 2

    rendered = render(parse_header(args.header))

    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            print(f"{args.output} is out of date; run scripts/generate_message_constants.py", file=sys.stderr)
            return 1
        print(f"{args.output} is up to date.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
