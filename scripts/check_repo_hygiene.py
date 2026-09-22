"""Keep build output from being committed again.

The repository had 116 files of build output in it -- bin/, obj/, out/ and a
copy of the bot's published assets -- which is how it reached 354 MB and
21,700 files. They are ignored now, but an ignore rule only helps until
somebody adds one with -f, so this checks the index rather than the disk.

    python scripts/check_repo_hygiene.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

# Directories whose contents are produced by a build and must never be tracked.
BUILD_OUTPUT_PREFIXES = (
    "bin/",
    "obj/",
    "out/",
    "src/data/bot-publish-test/",
)

# Individual files that are downloaded or generated rather than authored.
GENERATED_FILES = (
    "src/data/databases/babelcdb.zip",
    "bot_init_output.txt",
    ".coverage",
    "coverage.json",
    "coverage-current.json",
)

# Anything this large is almost certainly an asset that belongs elsewhere.
# The sounds and card databases predate this check and are allowed.
LARGE_FILE_LIMIT = 8 * 1024 * 1024
LARGE_FILE_ALLOWED_PREFIXES = ("src/data/",)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=str(ROOT), capture_output=True, text=True, check=True
    )
    return [line for line in result.stdout.splitlines() if line]


def main() -> int:
    try:
        files = tracked_files()
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Could not ask git what is tracked: {error}", file=sys.stderr)
        return 0  # Not a reason to block a commit.

    problems: list[str] = []

    build_output = [name for name in files if name.startswith(BUILD_OUTPUT_PREFIXES)]
    if build_output:
        problems.append(
            f"{len(build_output)} build output file(s) are tracked, starting with "
            f"{build_output[0]}. These are produced by a build; add them to "
            f".gitignore rather than committing them."
        )

    generated = [name for name in files if name in GENERATED_FILES]
    if generated:
        problems.append(
            f"generated file(s) are tracked: {', '.join(generated)}. "
            f"These are downloaded or produced locally."
        )

    oversized = []
    for name in files:
        if name.startswith(LARGE_FILE_ALLOWED_PREFIXES):
            continue
        path = ROOT / name
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > LARGE_FILE_LIMIT:
            oversized.append(f"{name} ({size / 1048576:.1f} MB)")
    if oversized:
        problems.append(f"unexpectedly large tracked file(s): {', '.join(oversized)}")

    if not problems:
        print(f"{len(files)} tracked files, no build output among them.")
        return 0

    print("Repository hygiene check failed:", file=sys.stderr)
    for problem in problems:
        print(f"  - {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
