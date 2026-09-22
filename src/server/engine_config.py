"""Resolve local EDOPro/ocgcore engine assets for the embedded server."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EnginePaths:
    ocgcore_path: str
    db_paths: list[str]
    script_dir: str

    @property
    def has_engine(self) -> bool:
        return bool(self.ocgcore_path and Path(self.ocgcore_path).exists())

    @property
    def has_databases(self) -> bool:
        return bool(self.db_paths)

    @property
    def has_scripts(self) -> bool:
        return bool(self.script_dir and Path(self.script_dir).exists())


def resolve_engine_paths(
    ocgcore_path: str = "",
    db_paths: list[str] | None = None,
    script_dir: str = "",
    root: Path | None = None,
) -> EnginePaths:
    """Resolve engine library, card databases, and script directory.

    Explicit arguments win, then environment variables, then common local
    project locations used by the bundled build script and EDOPro checkouts.
    """

    root = root or Path(__file__).resolve().parents[2]
    resolved_core = ocgcore_path or os.environ.get("YGOACCESS_OCGCORE", "")
    resolved_scripts = script_dir or os.environ.get("YGOACCESS_CARD_SCRIPTS", "")
    resolved_dbs = list(db_paths or [])

    if not resolved_core:
        for candidate in _ocgcore_candidates(root):
            if candidate.exists():
                resolved_core = str(candidate)
                break

    if not resolved_scripts:
        for candidate in _script_candidates(root):
            if candidate.exists():
                resolved_scripts = str(candidate)
                break

    if not resolved_dbs:
        env_dbs = os.environ.get("YGOACCESS_CDB_PATHS", "")
        if env_dbs:
            resolved_dbs = [p for p in env_dbs.split(os.pathsep) if p]
        else:
            resolved_dbs = [str(path) for path in _database_candidates(root)]

    return EnginePaths(resolved_core, resolved_dbs, resolved_scripts)


def _ocgcore_candidates(root: Path) -> list[Path]:
    system = platform.system()
    if system == "Windows":
        names: tuple[str, ...] = ("ocgcore.dll", "ocgcore64.dll", "ygopro-core.dll")
    elif system == "Darwin":
        names = ("libocgcore.dylib", "ocgcore.dylib")
    else:
        names = ("libocgcore.so", "ocgcore.so")

    folders = (
        root / "src" / "data" / "core",
        root / "data" / "core",
        root / "core",
        root,
    )
    return [folder / name for folder in folders for name in names]


def _script_candidates(root: Path) -> list[Path]:
    return [
        root / "src" / "data" / "scripts",
        root / "script",
        root / "scripts" / "cards",
        root / "data" / "scripts",
        root.parent / "CardScripts" / "script",
        root.parent / "ygopro-scripts",
        root.parent / "ygopro-scripts" / "script",
    ]


def _database_candidates(root: Path) -> list[Path]:
    folders = [
        root / "src" / "data" / "databases",
        root / "data" / "databases",
    ]
    results: list[Path] = []
    for folder in folders:
        if folder.exists():
            results.extend(sorted(folder.glob("*.cdb")))
    return results
