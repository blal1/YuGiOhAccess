"""MSG_SHUFFLE_SET_CARD: face down cards on the field were shuffled among their zones.

This is the message that makes a memorised board wrong: the same set cards are
still there, but which one sits in which zone has changed. Naming the affected
zones lets the player forget exactly the right ones instead of the whole board.

Wire format:

    u8 location (LOCATION_MZONE or LOCATION_SZONE)
    u8 count
    count x loc_info  -- where the cards were
    count x loc_info  -- where they ended up (all zeroes when the core does not say)

This handler used to be registered on id 34, which is MSG_REFRESH_DECK. The real
id is 36, so the announcement never fired.
"""

import io
import logging
import struct

from core import speech
from core import utils
from core.i18n import _
from game.card import card_constants
from game.card.location_conversion import LocationConversion
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_SHUFFLE_SET_CARD)
def msg_shuffle_set_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    location = client.read_u8(data)
    count = client.read_u8(data)
    previous = [client.read_location(data) for _unused in range(count)]
    current = []
    for _unused in range(count):
        try:
            current.append(client.read_location(data))
        except struct.error:
            # Some code paths only write the "before" block.
            logger.debug("MSG_SHUFFLE_SET_CARD carried no destination block")
            break
    logger.debug("Shuffle set cards: location=%s, count=%s", location, count)
    shuffle_set_card(client, location, previous, current)


def shuffle_set_card(client, location, previous, current):
    zones = describe_zones(client, previous)
    if zones:
        message = _("{count} set card(s) were shuffled between {zones}.").format(
            count=len(previous), zones=", ".join(zones)
        )
    else:
        message = _("{count} set card(s) on the field were shuffled.").format(count=len(previous))
    utils.output(message, priority=speech.Priority.CRITICAL)
    utils.get_ui_stack().play_duel_sound_effect("shuffle")


def describe_zones(client, locations):
    names = []
    for controller, location, sequence, _position in locations:
        if not location:
            continue
        try:
            converted = LocationConversion(client, controller, card_constants.LOCATION(location), sequence)
            readable = converted.to_human_readable()
        except (ValueError, AttributeError):
            logger.debug("Could not describe zone %s/%s/%s", controller, location, sequence)
            continue
        if readable and readable not in names:
            names.append(readable)
    return names
