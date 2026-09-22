import io

from core import utils

from game.card.card import Card
from game.card import card_constants

import logging
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_SUMMONING)
def msg_summoning(client, data, data_length, special=False):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    card = Card(code)
    controller, location, sequence, position = client.read_location(data)
    logger.debug(f"Position: {position}")
    card.set_location_and_position_info(controller, location, sequence, card_constants.POSITION(position))
    summoning(client, card, controller, location, sequence, position, special=special)
    return data.read()

@utils.duel_message_handler(message_constants.MSG_SUMMONED)
@utils.duel_message_handler(message_constants.MSG_SPSUMMONED)
def msg_summoned(client, data, data_length):
    return data[1:]

@utils.duel_message_handler(message_constants.MSG_SPSUMMONING)
def msg_summoning_special(client, data, data_length):
    msg_summoning(client, data, data_length, special=True)

def summoning(client, card, controller, location, sequence, position, special=False):
    card.set_location_and_position_info(controller, location, sequence, card_constants.POSITION(position))
    logger.debug(f"Summoning position: {card.position}")
    mine = card.controller == client.what_player_am_i
    # A link monster has no defense to read out. Numbers are safe to build a
    # string from; words are not, so only the numbers are assembled here.
    if card.type & card_constants.TYPE.LINK:
        stats = f"{card.attack}"
    else:
        stats = f"{card.attack}/{card.defense}"
    # The position came straight off the enum, so the player heard
    # "FACE UP ATTACK" in English whatever language they had chosen.
    position_name = card.get_position()
    if special and mine:
        message = _("You are special summoning {card} ({stats}) in {position} position.")
    elif special:
        message = _("Your opponent is special summoning {card} ({stats}) in {position} position.")
    elif mine:
        message = _("You are summoning {card} ({stats}) in {position} position.")
    else:
        message = _("Your opponent is summoning {card} ({stats}) in {position} position.")
    utils.output(message.format(card=card.get_name(), stats=stats, position=position_name))
