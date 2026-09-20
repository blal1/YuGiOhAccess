"""MSG_MISSED_EFFECT: an optional trigger effect lost its timing.

This is a rules fact a sighted player reads in the log window: the effect could
have activated but the window closed. Announcing it stops a blind player from
waiting for a prompt that will never come.

Wire format: loc_info (controller, location, sequence, position), u32 card code.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.card.card import Card
from game.card.location_conversion import LocationConversion
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_MISSED_EFFECT)
def msg_missed_effect(client, data, data_length):
    data = io.BytesIO(data[1:])
    controller, location, sequence, position = client.read_location(data)
    code = client.read_u32(data)
    card = Card(code)
    card.set_location_and_position_info(controller, location, sequence, position)
    missed_effect(client, card)


def missed_effect(client, card):
    try:
        where = LocationConversion.from_card_location(client, card).to_human_readable()
    except (ValueError, AttributeError, TypeError):
        # The card can sit somewhere the field does not model, e.g. an overlay.
        logger.debug("Could not resolve location for missed effect on %s", card.get_name())
        where = ""
    if card.controller == client.what_player_am_i:
        message = _("Your {name} missed its timing.")
    else:
        message = _("Your opponent's {name} missed its timing.")
    text = message.format(name=card.get_name())
    if where:
        text = _("{message} ({location})").format(message=text, location=where)
    utils.output(text, priority=speech.Priority.INFO)
