"""MSG_HINT: the running commentary the core offers alongside a prompt.

Most of these carry an effect description code, not text. Reading the code out
as a number told the player nothing: "Select a card to send to the graveyard"
was spoken as "12582914".

The one that matters most is SELECTMSG, which is the core explaining what the
selection prompt that follows is *for*. A sighted player reads it above the
card list; without it a blind player is handed a list of cards and no reason.
"""

import io
import logging
from enum import IntFlag

from core import speech
from core import utils
from core import variables
from core.i18n import _
from game.card.card import Card
from game.edo import message_constants
from ui.duel_messages.player_hint import describe_effect

logger = logging.getLogger(__name__)


class HINT(IntFlag):
    EVENT = 1
    MESSAGE = 2
    SELECTMSG = 3
    OPSELECTED = 4
    EFFECT = 5
    RACE = 6
    ATTRIB = 7
    CODE = 8
    NUMBER = 9
    CARD = 10
    ZONE = 11


def _card_name(code):
    try:
        return Card(code).get_name()
    except Exception:
        logger.debug("Hint named a card we could not load: %s", code, exc_info=True)
        return ""


def _system_string(string_id):
    strings = getattr(variables.LANGUAGE_HANDLER, "strings", None) or {}
    return strings.get("system", {}).get(string_id, "")


@utils.duel_message_handler(message_constants.MSG_HINT)
def msg_hint(client, data, length):
    data = io.BytesIO(data[1:])
    htype = client.read_u8(data)
    try:
        hint_type = HINT(htype)
    except ValueError:
        logger.debug("Unknown hint type %s", htype)
        return None
    player = client.read_u8(data)
    value = client.read_u64(data)
    return hint(client, hint_type, player, value)


def hint(client, hint_type, player, data):
    mine = player == getattr(client, "what_player_am_i", -1)

    if hint_type == HINT.MESSAGE:
        text = describe_effect(data)
        if text:
            utils.output(str(text))
        else:
            logger.debug("Hint message %s has no readable description", data)
        return

    if hint_type == HINT.SELECTMSG:
        # Why the prompt that follows is being asked. Only the player being
        # asked needs it; the other one is only watching.
        if not mine:
            return
        text = describe_effect(data) or _card_name(data)
        if text:
            utils.output(str(text), priority=speech.Priority.CRITICAL)
        else:
            logger.debug("Selection hint %s has no readable description", data)
        return

    if hint_type == HINT.OPSELECTED:
        text = describe_effect(data)
        if text:
            if mine:
                utils.output(_("You selected: {choice}").format(choice=text))
            else:
                utils.output(_("Your opponent selected: {choice}").format(choice=text))
        return

    if hint_type == HINT.NUMBER:
        template = _system_string(1512)
        utils.output(template % data if template else str(data))
        return

    if hint_type in (HINT.CODE, HINT.CARD):
        name = _card_name(data)
        if name:
            utils.output(_("Hint: {card}").format(card=name))
        return

    logger.debug(f"Hint type: {hint_type}, player: {player}, data: {data}")
