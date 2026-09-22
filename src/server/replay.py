"""The record of a duel, as the core told it.

A .yrp is EDOPro's own binary replay, and only EDOPro's server writes one. The
bundled server cannot produce a file that EDOPro would open, and pretending
otherwise -- naming our bytes .yrp and hoping -- would be worse than not
sending anything: the player would collect files that no program can read.

So this is our own container, with its own magic so it can never be mistaken
for a yrp, holding exactly what the core emitted, in order. That is enough to
replay a duel through the same message handlers that played it the first time.
"""

from __future__ import annotations

import logging
import struct

logger = logging.getLogger(__name__)

# What our replays start with, so a reader can tell them from a real yrp at a
# glance. Bumped if the layout after the header ever changes.
MAGIC = b"YGOAREP1"
HEADER = struct.Struct("<8sII")

# Refuse to grow past this. A duel that somehow never ends should not take the
# server's memory with it.
MAX_MESSAGES = 100_000


class DuelReplay:
    """Every message the core produced during one duel."""

    def __init__(self):
        self._messages: list[bytes] = []
        self._overflowed = False

    def add(self, msg_data: bytes):
        if len(self._messages) >= MAX_MESSAGES:
            if not self._overflowed:
                logger.warning("Replay is full at %d messages; not recording more", MAX_MESSAGES)
                self._overflowed = True
            return
        self._messages.append(bytes(msg_data))

    def __len__(self) -> int:
        return len(self._messages)

    def to_bytes(self) -> bytes:
        if not self._messages:
            return b""
        out = bytearray(HEADER.pack(MAGIC, 0, len(self._messages)))
        for message in self._messages:
            out += struct.pack("<I", len(message))
            out += message
        return bytes(out)


def is_ours(data: bytes) -> bool:
    """Whether these bytes are one of our replays rather than a yrp."""
    return bool(data) and bytes(data[:len(MAGIC)]) == MAGIC


def read(data: bytes) -> list[bytes]:
    """The messages in one of our replays, or an empty list if it is not one."""
    if not is_ours(data) or len(data) < HEADER.size:
        return []
    _magic, _flags, count = HEADER.unpack_from(data, 0)
    offset = HEADER.size
    messages: list[bytes] = []
    for _ in range(count):
        if offset + 4 > len(data):
            logger.warning("Replay ended early: expected %d messages, found %d", count, len(messages))
            break
        (length,) = struct.unpack_from("<I", data, offset)
        offset += 4
        if offset + length > len(data):
            logger.warning("Replay message runs past the end of the file")
            break
        messages.append(data[offset:offset + length])
        offset += length
    return messages
