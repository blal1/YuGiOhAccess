"""What each duelist is allowed to see.

ocgcore has no notion of a recipient: every message and every query it produces
contains the whole truth, including the card codes of the opponent's hand and of
face-down cards. Relaying those buffers unchanged hands one player the other's
private information, so the server rewrites them per recipient before sending.

Two mechanisms, because the core offers two shapes:

* query buffers (MSG_UPDATE_DATA) carry a QUERY_IS_PUBLIC field per card, which
  is the core's own answer to "may anyone see this?". Identity fields of a card
  that is not public are zeroed for everyone but its controller.
* duel messages carry raw codes with a location and a position, so visibility is
  decided from those.

Zeroing rather than dropping matters: every chunk declares its own length, and
the client reads a code of 0 as "a card I am not allowed to know about".
"""

import logging
import struct

from game.card import card_constants
from game.edo.message_constants import (
    MSG_DRAW,
    MSG_MOVE,
    MSG_SHUFFLE_EXTRA,
    MSG_SHUFFLE_HAND,
)

logger = logging.getLogger(__name__)

QUERY_END = 0x80000000
QUERY_IS_PUBLIC = 0x100000

# OCG_DuelQueryLocation prepends the byte count of everything that follows, and
# that word is what the client reads as the buffer size. It is not a chunk, so
# walking the chunks has to start after it.
QUERY_LENGTH_PREFIX = 4

# Fields that say which card this is. Everything else (position, counters,
# overlay units, link markers) stays, so the recipient still sees that a card is
# there and what state it is in.
IDENTITY_QUERY_FLAGS = frozenset({
    0x1,        # CODE
    0x4,        # ALIAS
    0x8,        # TYPE
    0x10,       # LEVEL
    0x20,       # RANK
    0x40,       # ATTRIBUTE
    0x80,       # RACE
    0x100,      # ATTACK
    0x200,      # DEFENSE
    0x400,      # BASE_ATTACK
    0x800,      # BASE_DEFENSE
    0x200000,   # LSCALE
    0x400000,   # RSCALE
    0x800000,   # LINK
})

# No seat, so nothing private is visible. Used for observers.
NO_SEAT = -1


def iter_query_chunks(buffer: bytes, offset: int = 0):
    """Yield (start, end, flag) for every chunk, plus (start, end, None) for a
    zero length chunk, which the core uses for an empty zone."""
    total = len(buffer)
    while offset + 2 <= total:
        size = struct.unpack_from("<H", buffer, offset)[0]
        if size == 0:
            yield offset, offset + 2, None
            offset += 2
            continue
        end = offset + 2 + size
        if end > total:
            logger.warning(
                "Query chunk at %d claims %d bytes but only %d remain", offset, size, total - offset - 2
            )
            return
        flag = struct.unpack_from("<I", buffer, offset + 2)[0]
        yield offset, end, flag
        offset = end


def redact_query_buffer(buffer: bytes, reveal: bool) -> bytes:
    """Blank the identity of every non public card unless reveal is set.

    reveal is true for the player who controls the queried location: your own
    face-down cards and your own hand are yours to know.
    """
    if reveal or len(buffer) <= QUERY_LENGTH_PREFIX:
        return buffer

    out = bytearray(buffer)
    card_chunks: list[tuple[int, int, int]] = []
    is_public = None

    for start, end, flag in iter_query_chunks(buffer, QUERY_LENGTH_PREFIX):
        if flag is None:
            card_chunks.clear()
            is_public = None
            continue
        if flag == QUERY_IS_PUBLIC:
            is_public = buffer[start + 6] != 0
        elif flag == QUERY_END:
            if is_public is None:
                # Without the core's own answer there is no safe way to tell,
                # so the card stays hidden rather than leaking by default.
                logger.warning("Query for a card carried no QUERY_IS_PUBLIC; hiding it")
            if not is_public:
                for chunk_start, chunk_end, chunk_flag in card_chunks:
                    if chunk_flag in IDENTITY_QUERY_FLAGS:
                        out[chunk_start + 6:chunk_end] = bytes(chunk_end - chunk_start - 6)
            card_chunks.clear()
            is_public = None
            continue
        card_chunks.append((start, end, flag))

    return bytes(out)


def card_visible_to(recipient: int, controller: int, location: int, position: int) -> bool:
    """Whether recipient may know the identity of a card in this spot.

    Overlay units are public. A deck is private to everyone, including its
    owner. Anything face-up is public, and anything else is known only to the
    player who controls it.
    """
    if location & card_constants.LOCATION.OVERLAY:
        return True
    if location & card_constants.LOCATION.DECK:
        return False
    if position & card_constants.POSITION.FACE_UP:
        return True
    return recipient == controller


def redact_message(msg_type: int, msg_data: bytes, recipient: int) -> bytes:
    """Rewrite a duel message so it only tells recipient what it may know."""
    if msg_type == MSG_DRAW:
        return _redact_draw(msg_data, recipient)
    if msg_type in (MSG_SHUFFLE_HAND, MSG_SHUFFLE_EXTRA):
        return _redact_shuffle(msg_data, recipient)
    if msg_type == MSG_MOVE:
        return _redact_move(msg_data, recipient)
    return msg_data


def _redact_draw(msg_data: bytes, recipient: int) -> bytes:
    """MSG_DRAW: u8 player, u32 count, count * (u32 code, u32 position)."""
    if len(msg_data) < 6:
        return msg_data
    player = msg_data[1]
    count = struct.unpack_from("<I", msg_data, 2)[0]
    out = bytearray(msg_data)
    offset = 6
    for _ in range(count):
        if offset + 8 > len(msg_data):
            break
        position = struct.unpack_from("<I", msg_data, offset + 4)[0]
        if not card_visible_to(recipient, player, card_constants.LOCATION.HAND, position):
            struct.pack_into("<I", out, offset, 0)
        offset += 8
    return bytes(out)


def _redact_shuffle(msg_data: bytes, recipient: int) -> bytes:
    """MSG_SHUFFLE_HAND / MSG_SHUFFLE_EXTRA: u8 player, u32 count, count * u32 code."""
    if len(msg_data) < 6:
        return msg_data
    player = msg_data[1]
    if recipient == player:
        return msg_data
    count = struct.unpack_from("<I", msg_data, 2)[0]
    out = bytearray(msg_data)
    offset = 6
    for _ in range(count):
        if offset + 4 > len(msg_data):
            break
        struct.pack_into("<I", out, offset, 0)
        offset += 4
    return bytes(out)


def read_location(msg_data: bytes, offset: int):
    """Read one location reference, returning it and the next offset.

    A location is u8 controller, u8 location, u32 sequence and -- only when the
    overlay bit is clear -- u32 position. An overlay reference is two words
    shorter, so this cannot be read at a fixed offset.
    """
    controller = msg_data[offset]
    location = msg_data[offset + 1]
    sequence = struct.unpack_from("<I", msg_data, offset + 2)[0]
    offset += 6
    position = 0
    if not location & card_constants.LOCATION.OVERLAY:
        position = struct.unpack_from("<I", msg_data, offset)[0]
        offset += 4
    return (controller, location, sequence, position), offset


def _redact_move(msg_data: bytes, recipient: int) -> bytes:
    """MSG_MOVE: u32 code, previous location, current location, u32 reason."""
    try:
        previous, offset = read_location(msg_data, 5)
        current, _ = read_location(msg_data, offset)
    except (IndexError, struct.error):
        logger.warning("MSG_MOVE too short to redact (%d bytes)", len(msg_data))
        return msg_data

    # A card that left the field has no current location; where it came from
    # still decides whether the recipient saw it.
    controller, location, _sequence, position = current if current[1] else previous
    if card_visible_to(recipient, controller, location, position):
        return msg_data
    out = bytearray(msg_data)
    struct.pack_into("<I", out, 1, 0)
    return bytes(out)
