"""Readable summaries of the choices the core offers a player.

"The bot ended its turn without doing anything" has two very different causes,
and the prompt tells them apart: either the core offered it nothing, or it
offered plays the bot failed to recognise. The routing log shows that a prompt
was sent; this shows what was in it.

Only used for logging, so every reader is defensive: a summary that cannot be
produced must never interfere with the duel.
"""

import logging
import struct

from game.edo.message_constants import MSG_SELECT_BATTLECMD, MSG_SELECT_IDLECMD

logger = logging.getLogger(__name__)

IDLE_CATEGORIES = ("summonable", "special summonable", "repositionable",
                   "monster settable", "spell settable")


class _Reader:
    def __init__(self, data: bytes, offset: int = 0):
        self.data = data
        self.offset = offset

    def u8(self) -> int:
        value = self.data[self.offset]
        self.offset += 1
        return value

    def u32(self) -> int:
        value = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return value

    def u64(self) -> int:
        value = struct.unpack_from("<Q", self.data, self.offset)[0]
        self.offset += 8
        return value

    def card_list(self, sequence_bytes: int = 4, extra: bool = False) -> list:
        cards = []
        for _ in range(self.u32()):
            code = self.u32()
            controller = self.u8()
            location = self.u8()
            sequence = self.u32() if sequence_bytes == 4 else self.u8()
            if extra:
                self.u64()
                self.u8()
            cards.append((code, controller, location, sequence))
        return cards


def summarise_idle(msg_data: bytes) -> str:
    """What a MSG_SELECT_IDLECMD is actually offering."""
    reader = _Reader(msg_data, 2)  # skip the message id and the player
    parts = []
    for name in IDLE_CATEGORIES:
        cards = reader.card_list(sequence_bytes=1 if name == "repositionable" else 4)
        if cards:
            parts.append(f"{name}={[hex(c[0]) for c in cards]}")
    activatable = reader.card_list(extra=True)
    if activatable:
        parts.append(f"activatable={[hex(c[0]) for c in activatable]}")
    to_bp = reader.u8()
    to_ep = reader.u8()
    if to_bp:
        parts.append("can enter battle phase")
    if to_ep:
        parts.append("can end turn")
    return "; ".join(parts) if parts else "nothing at all"


def summarise_battle(msg_data: bytes) -> str:
    """What a MSG_SELECT_BATTLECMD is actually offering."""
    reader = _Reader(msg_data, 2)
    parts = []
    activatable = reader.card_list(extra=True)
    if activatable:
        parts.append(f"activatable={[hex(c[0]) for c in activatable]}")
    attackers = []
    for _ in range(reader.u32()):
        code = reader.u32()
        reader.u8()   # controller
        reader.u8()   # location
        reader.u8()   # sequence
        reader.u8()   # can attack directly
        attackers.append(code)
    if attackers:
        parts.append(f"can attack={[hex(code) for code in attackers]}")
    if reader.u8():
        parts.append("can enter main phase 2")
    if reader.u8():
        parts.append("can end turn")
    return "; ".join(parts) if parts else "nothing at all"


def summarise(msg_type: int, msg_data: bytes) -> str | None:
    """A one line summary of a prompt, or None if there is nothing to add."""
    try:
        if msg_type == MSG_SELECT_IDLECMD:
            return summarise_idle(msg_data)
        if msg_type == MSG_SELECT_BATTLECMD:
            return summarise_battle(msg_data)
    except Exception:
        logger.debug("Could not summarise a prompt for the log", exc_info=True)
    return None
