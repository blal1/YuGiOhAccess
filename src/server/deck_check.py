"""Is this deck legal for this room?

The server used to take any deck at all. A deck of three cards started a duel
the core could not run; sixty copies of one card started one nobody could win.
Everything was left to the client, which meant everything was left to whoever
wrote the client -- and the bot does not use ours.

The error is reported the way EDOPro reports it, as a deck error inside
STOC_ERROR_MSG, so a client that already understands those needs no changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from game.edo import structs

logger = logging.getLogger(__name__)

# ERRMSG_DECKERROR: which kind of message this is inside STOC_ERROR_MSG.
ERRMSG_DECKERROR = 2

# The reasons a deck can be refused, as EDOPro numbers them.
DECKERROR_LFLIST = 1
DECKERROR_UNKNOWNCARD = 4
DECKERROR_CARDCOUNT = 5
DECKERROR_MAINCOUNT = 6
DECKERROR_EXTRACOUNT = 7
DECKERROR_SIDECOUNT = 8

# What a banlist allows when it says nothing about a card.
DEFAULT_COPY_LIMIT = 3


@dataclass(frozen=True)
class DeckError:
    """Why a deck was refused, in the shape the client reads it back."""

    type: int
    got: int = 0
    minimum: int = 0
    maximum: int = 0
    code: int = 0

    def to_bytes(self) -> bytes:
        """Built from the client's own structure, so the layout cannot drift."""
        message = structs.DeckErrrorMSG()
        message.msg = ERRMSG_DECKERROR
        message.type = self.type
        message.count.got = self.got
        message.count.min = self.minimum
        message.count.max = self.maximum
        message.code = self.code
        return bytes(message)


def _boundary(limits, name, fallback_min, fallback_max):
    boundary = getattr(limits, name, None)
    if boundary is None:
        return fallback_min, fallback_max
    return int(boundary.min), int(boundary.max)


def check_deck(main, extra, side, limits=None, banlist=None, known_card=None) -> DeckError | None:
    """The first thing wrong with this deck, or None if nothing is.

    ``limits`` is the room's DeckLimits, ``banlist`` anything with a
    ``get_limit(code)``, and ``known_card`` a predicate for whether a card
    exists at all. Each is optional: a check we cannot make is one we skip,
    because refusing a deck for a reason we cannot establish is worse than
    letting the core refuse it later.
    """
    main = list(main)
    extra = list(extra)
    side = list(side)

    main_min, main_max = _boundary(limits, "main", 40, 60)
    extra_min, extra_max = _boundary(limits, "extra", 0, 15)
    side_min, side_max = _boundary(limits, "side", 0, 15)

    if not main_min <= len(main) <= main_max:
        return DeckError(DECKERROR_MAINCOUNT, len(main), main_min, main_max)
    if not extra_min <= len(extra) <= extra_max:
        return DeckError(DECKERROR_EXTRACOUNT, len(extra), extra_min, extra_max)
    if not side_min <= len(side) <= side_max:
        return DeckError(DECKERROR_SIDECOUNT, len(side), side_min, side_max)

    everything = main + extra + side
    if known_card is not None:
        for code in everything:
            if not known_card(code):
                return DeckError(DECKERROR_UNKNOWNCARD, code=code)

    counts: dict[int, int] = {}
    for code in everything:
        counts[code] = counts.get(code, 0) + 1
    for code, count in counts.items():
        limit = DEFAULT_COPY_LIMIT
        reason = DECKERROR_CARDCOUNT
        if banlist is not None:
            try:
                limit = int(banlist.get_limit(code))
                reason = DECKERROR_LFLIST
            except Exception:
                logger.debug("Banlist could not rule on card %s", code, exc_info=True)
        if count > limit:
            return DeckError(reason, count, 0, limit, code)
    return None


def describe(error: DeckError) -> str:
    """One line for the log. The client says it properly to the player."""
    if error.type == DECKERROR_MAINCOUNT:
        return f"main deck has {error.got} cards, not {error.minimum} to {error.maximum}"
    if error.type == DECKERROR_EXTRACOUNT:
        return f"extra deck has {error.got} cards, at most {error.maximum} allowed"
    if error.type == DECKERROR_SIDECOUNT:
        return f"side deck has {error.got} cards, at most {error.maximum} allowed"
    if error.type == DECKERROR_UNKNOWNCARD:
        return f"card {error.code} is not in the card database"
    if error.type == DECKERROR_LFLIST:
        return f"card {error.code} appears {error.got} times, banlist allows {error.maximum}"
    if error.type == DECKERROR_CARDCOUNT:
        return f"card {error.code} appears {error.got} times, at most {error.maximum} allowed"
    return f"deck error {error.type}"
