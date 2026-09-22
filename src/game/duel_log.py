"""A duel, written down so it can be read back after the fact.

The replay viewer used to list files and read their size out. There was
nothing to play: offline duels recorded nothing at all, because the bundled
server never sends the replay packets, and what an online server did send was
appended raw and never parsed again.

What a screen reader user actually wants from a replay is the duel in words,
in order, at their own pace. The client already builds exactly that while the
duel runs -- every announcement and every choice the player made lands in
``core.speech.MESSAGE_LOG`` -- so a duel log is that history, saved.

The format is plain JSON with a version on it. It is ours, it is readable in
any text editor, and it is deliberately not called a .yrp: a yrp is the
core's own binary replay, which only a server can produce.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
SUFFIX = ".duel.json"


def entry_to_dict(entry, started_at: float) -> dict:
    """One history entry, with its time measured from the start of the duel."""
    from core import speech

    return {
        "at": round(max(0.0, entry.at - started_at), 3),
        "kind": "action" if entry.kind == speech.Kind.ACTION else "message",
        "text": str(entry.text),
    }


def build(entries, **metadata) -> dict:
    """Turn a run of speech log entries into a saveable duel log."""
    entries = list(entries)
    started_at = entries[0].at if entries else 0.0
    log = {
        "version": FORMAT_VERSION,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
        "entries": [entry_to_dict(entry, started_at) for entry in entries],
    }
    log.update({key: value for key, value in metadata.items() if value is not None})
    return log


def write(path: Path, entries, **metadata) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    log = build(entries, **metadata)
    path.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    logger.info("Wrote duel log %s (%d entries)", path, len(log["entries"]))
    return path


def read(path: Path) -> dict | None:
    """Load a duel log, or None if it is not one we can read."""
    try:
        log = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        logger.warning("Could not read the duel log %s: %s", path, error)
        return None
    if not isinstance(log, dict) or "entries" not in log:
        logger.warning("%s is not a duel log", path)
        return None
    if log.get("version") != FORMAT_VERSION:
        logger.warning("Duel log %s is version %s, not %s", path, log.get("version"), FORMAT_VERSION)
    return log


def format_line(entry: dict) -> str:
    """One readable line: when it happened, and what it was.

    Actions are marked, because "did I ask for that?" is the question a player
    has when a duel does something they did not expect.
    """
    from core.i18n import _

    elapsed = int(entry.get("at", 0))
    stamp = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
    text = entry.get("text", "")
    if entry.get("kind") == "action":
        return _("{time} You: {text}").format(time=stamp, text=text)
    return _("{time} {text}").format(time=stamp, text=text)


def lines(log: dict) -> list[str]:
    return [format_line(entry) for entry in log.get("entries", [])]


def summary(log: dict) -> str:
    """A one line description, for the list of saved duels."""
    from core.i18n import _

    entries = log.get("entries", [])
    length = int(entries[-1]["at"]) if entries else 0
    return _("{count} entries, {minutes} minutes, recorded {when}").format(
        count=len(entries),
        minutes=max(1, round(length / 60)),
        when=log.get("recorded_at", _("at an unknown time")),
    )
