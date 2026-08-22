"""Build WindBot.Desktop.dll for embedding via pythonnet.

Requirements: .NET 6+ SDK (dotnet CLI)

Usage:
    python scripts/build_windbot.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSPROJ = ROOT / "WindBot.Desktop.csproj"
OUTPUT_DIR = ROOT / "src" / "data" / "bot"


def main():
    if not shutil.which("dotnet"):
        print("ERROR: dotnet CLI not found. Install .NET 6+ SDK.", file=sys.stderr)
        sys.exit(1)

    print(f"Publishing {CSPROJ.name}...")
    result = subprocess.run(
        ["dotnet", "publish", str(CSPROJ), "-c", "Release", "-o", str(OUTPUT_DIR)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("Build FAILED:", file=sys.stderr)
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    print(f"Publish succeeded. Output: {OUTPUT_DIR}")
    dll = OUTPUT_DIR / "WindBot.Desktop.dll"
    if dll.exists():
        print(f"  {dll.name} ({dll.stat().st_size / 1024:.0f} KB)")
    else:
        print("WARNING: DLL not found in output directory", file=sys.stderr)


if __name__ == "__main__":
    main()
