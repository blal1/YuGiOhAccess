"""MSG_PLAYER_HINT: per player effect reminders.

The core sends one of these whenever a continuous effect that targets a player
(rather than a card) starts or stops applying: "you cannot special summon this
turn", "your opponent skips their next draw phase", and so on. A sighted player
reads them off a persistent list next to their life points; without a handler a
blind player never learns about them at all.

This module keeps that list per player and announces the changes. The current
list is readable on demand through :func:`get_player_hints_text`.

Wire format: u8 player, u8 hint type, u64 effect description.

This handler used to be registered on id 82, which ocgcore does not define, so
it never ran. The real id is 165.
"""

import io
import logging

from core import speech
from core import utils
from core import variables
from core.i18n import _
from game.card.card import Card
from game.edo import message_constants

logger = logging.getLogger(__name__)

# ocgapi_constants.h
PHINT_DESC_ADD = 6
PHINT_DESC_REMOVE = 7

# player index -> list of active effect descriptions
_player_hints: dict[int, list[str]] = {0: [], 1: []}


def reset_player_hints():
    """Forget every hint. Called when a new duel starts."""
    _player_hints[0] = []
    _player_hints[1] = []


def get_player_hints(player):
    return list(_player_hints.get(player, []))


@utils.duel_message_handler(message_constants.MSG_PLAYER_HINT)
def msg_player_hint(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    hint_type = client.read_u8(data)
    description = client.read_u64(data)
    logger.debug("Player hint: player=%s, type=%s, description=%s", player, hint_type, description)
    player_hint(client, player, hint_type, description)


def player_hint(client, player, hint_type, description):
    text = describe_effect(description)
    if not text:
        logger.debug("Player hint %s has no readable description", description)
        return
    hints = _player_hints.setdefault(player, [])
    is_yours = player == client.what_player_am_i
    if hint_type == PHINT_DESC_ADD:
        hints.append(text)
        message = _("New effect on you: {effect}") if is_yours else _("New effect on your opponent: {effect}")
    elif hint_type == PHINT_DESC_REMOVE:
        if text in hints:
            hints.remove(text)
        message = _("Effect on you ended: {effect}") if is_yours else _("Effect on your opponent ended: {effect}")
    else:
        logger.debug("Unhandled player hint type %s", hint_type)
        return
    utils.output(message.format(effect=text), priority=speech.Priority.INFO)


def describe_effect(description):
    """Resolve an effect description code to text.

    Values above 10000 pack a card code in the upper bits and an index into that
    card's strings in the lower four; smaller values index the system strings.

    Anything that is not one of those is handed back as it stands: these codes
    arrive from the wire, and a hint that cannot be resolved is worth saying
    nothing about rather than taking the handler down.
    """
    if not isinstance(description, int):
        return str(description) if description else ""
    try:
        if description > 10000:
            return Card(description >> 4).get_effect_description(description, True)
    except Exception:
        logger.debug("Could not describe effect %s", description, exc_info=True)
        return ""
    strings = getattr(variables.LANGUAGE_HANDLER, "strings", None)
    if not strings:
        return ""
    return strings.get("system", {}).get(description, "")


def get_player_hints_text(client):
    """A readable summary of every effect currently applying to either player."""
    you = client.what_player_am_i if client.what_player_am_i in (0, 1) else 0
    mine = get_player_hints(you)
    theirs = get_player_hints(1 - you)
    if not mine and not theirs:
        return _("No effects are currently applying to either player.")
    lines = []
    if mine:
        lines.append(_("Applying to you:"))
        lines.extend(mine)
    if theirs:
        lines.append(_("Applying to your opponent:"))
        lines.extend(theirs)
    return "\n".join(lines)
