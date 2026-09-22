"""Screen reader speech queue: priorities and a replayable message history.

Two problems this solves:

* ``utils.output()`` only speaks while the application window is focused. Alt
  tabbing during the opponent's turn used to drop duel messages with no trace.
  Everything now lands in :data:`MESSAGE_LOG` whether or not it was spoken, so
  the player can replay what they missed.
* Every message used to be equal, so an attack announcement queued behind a
  phase change. Messages now carry a :class:`Priority`; critical ones interrupt
  whatever is being read, ambient ones step aside for them.

The log is deliberately dumb and in-memory: it is a reading aid, not state.
"""

import threading
import time
from collections import deque, namedtuple
from enum import IntEnum

# How long (seconds) an ambient message stays suppressed after a critical one.
AMBIENT_SUPPRESSION_WINDOW = 1.5

# How many entries the log keeps. It doubles as the in duel history, so it
# holds a whole duel's worth rather than just the last few announcements.
HISTORY_CAPACITY = 500

# How many messages "read the recent messages" reads out by default.
DEFAULT_REPLAY_COUNT = 10


class Priority(IntEnum):
    """How urgently a message needs the screen reader.

    AMBIENT
        Flavour and bookkeeping (shuffles, phase bookkeeping). Skipped while a
        critical announcement is still being read.
    INFO
        The default. Queued normally, never interrupts.
    CRITICAL
        Must be heard now: attacks, targeting, damage, resyncs, match results.
        Interrupts whatever is currently being spoken.
    """

    AMBIENT = 0
    INFO = 1
    CRITICAL = 2


class Kind(IntEnum):
    """Where an entry came from.

    MESSAGE
        Something the duel told us: a draw, a summon, a phase change.
    ACTION
        Something the player did: the menu item they activated.

    Keeping both in one stream is the point. A history that lists only what
    happened cannot answer "did I ask for that?", which is the question a
    player has when the duel does something they did not expect.
    """

    MESSAGE = 0
    ACTION = 1


LogEntry = namedtuple("LogEntry", "at text priority spoken kind")


class MessageLog:
    """Thread safe ring buffer of everything that was sent to the screen reader."""

    def __init__(self, capacity: int = HISTORY_CAPACITY):
        self._entries: deque[LogEntry] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._last_critical_at = 0.0

    def add(self, message: str, priority: "Priority" = Priority.INFO, spoken: bool = True,
            kind: "Kind" = Kind.MESSAGE) -> None:
        now = time.monotonic()
        with self._lock:
            self._entries.append(LogEntry(now, str(message), priority, spoken, kind))
            if spoken and priority >= Priority.CRITICAL:
                self._last_critical_at = now

    def recent(self, count: int = DEFAULT_REPLAY_COUNT) -> list[str]:
        """Return the last ``count`` messages, oldest first.

        Actions are left out: this feeds the spoken replay, and the player does
        not need their own menu choices read back at them.
        """
        if count <= 0:
            return []
        with self._lock:
            entries = [entry for entry in self._entries if entry.kind == Kind.MESSAGE]
        return [entry.text for entry in entries[-count:]]

    def entries(self, count: int | None = None) -> list[LogEntry]:
        """Return the whole stream, actions included, oldest first."""
        with self._lock:
            entries = list(self._entries)
        if count is not None and count > 0:
            entries = entries[-count:]
        return entries

    def missed(self) -> list[str]:
        """Return the messages that were logged but never spoken."""
        with self._lock:
            return [
                entry.text for entry in self._entries
                if not entry.spoken and entry.kind == Kind.MESSAGE
            ]

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._last_critical_at = 0.0

    def critical_recently_spoken(self, window: float = AMBIENT_SUPPRESSION_WINDOW) -> bool:
        with self._lock:
            if not self._last_critical_at:
                return False
            return (time.monotonic() - self._last_critical_at) < window

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


MESSAGE_LOG = MessageLog()


class _CatchUpState:
    """Whether the server is currently replaying a backlog at us.

    During a catch up (rejoin, spectator join, recovery after lag) the server
    fires hundreds of duel messages in a burst. Speaking all of them is useless
    and takes minutes, so they are logged and left out of the speech stream; the
    player gets a summary at the end and can replay them.
    """

    def __init__(self):
        self.active = False
        self._suppressed = 0
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            self.active = True
            self._suppressed = 0

    def note_suppressed(self):
        with self._lock:
            self._suppressed += 1

    def finish(self):
        with self._lock:
            self.active = False
            suppressed, self._suppressed = self._suppressed, 0
            return suppressed


CATCH_UP = _CatchUpState()
