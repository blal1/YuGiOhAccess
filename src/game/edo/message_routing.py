"""Which duel messages address a single player, and how to name them in logs.

Both sides of a local duel need this: the bundled server uses it to decide who
receives a message, and the client uses it to tell a prompt meant for it apart
from one it is only watching. Keeping one table means the two can never drift.
"""

from game.edo.message_constants import (
    MSG,
    MSG_ANNOUNCE_ATTRIB,
    MSG_ANNOUNCE_CARD,
    MSG_ANNOUNCE_NUMBER,
    MSG_ANNOUNCE_RACE,
    MSG_CONFIRM_CARDS,
    MSG_DRAW,
    MSG_ROCK_PAPER_SCISSORS,
    MSG_SELECT_BATTLECMD,
    MSG_SELECT_CARD,
    MSG_SELECT_CHAIN,
    MSG_SELECT_COUNTER,
    MSG_SELECT_DISFIELD,
    MSG_SELECT_EFFECTYN,
    MSG_SELECT_IDLECMD,
    MSG_SELECT_OPTION,
    MSG_SELECT_PLACE,
    MSG_SELECT_POSITION,
    MSG_SELECT_SUM,
    MSG_SELECT_TRIBUTE,
    MSG_SELECT_UNSELECT_CARD,
    MSG_SELECT_YESNO,
    MSG_SORT_CARD,
    MSG_SORT_CHAIN,
)

# The core is blocked on a response from exactly one player, whose index is the
# first byte of the message body.
PROMPT_MESSAGES = frozenset({
    MSG_SELECT_BATTLECMD, MSG_SELECT_IDLECMD, MSG_SELECT_EFFECTYN,
    MSG_SELECT_YESNO, MSG_SELECT_OPTION, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
    MSG_SELECT_PLACE, MSG_SELECT_DISFIELD, MSG_SELECT_POSITION,
    MSG_SELECT_TRIBUTE, MSG_SELECT_COUNTER, MSG_SELECT_SUM,
    MSG_SELECT_UNSELECT_CARD, MSG_SORT_CARD, MSG_SORT_CHAIN,
    MSG_ANNOUNCE_RACE, MSG_ANNOUNCE_ATTRIB, MSG_ANNOUNCE_CARD,
    MSG_ANNOUNCE_NUMBER, MSG_ROCK_PAPER_SCISSORS,
})

# Also addressed to one player, but reporting rather than asking, so both sides
# need them to keep their board in sync.
PLAYER_INFO_MESSAGES = frozenset({MSG_DRAW, MSG_CONFIRM_CARDS})


def message_name(msg_type: int) -> str:
    """Human readable duel message name, for logs."""
    try:
        return MSG(msg_type).name
    except ValueError:
        return f"UNKNOWN({msg_type})"


def addressed_player(msg_type: int, msg_data: bytes):
    """Player index a message is addressed to, or None if it is for everyone."""
    if len(msg_data) < 2:
        return None
    if msg_type in PROMPT_MESSAGES or msg_type in PLAYER_INFO_MESSAGES:
        return msg_data[1]
    return None
