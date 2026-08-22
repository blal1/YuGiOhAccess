import io
import logging

from game.card import card_constants

from core import utils
from core.i18n import _
from core import variables

logger = logging.getLogger(__name__)

@utils.duel_message_handler(160)
def msg_card_hint(client, data, data_length):
    data = io.BytesIO(data[1:])
    loc = client.read_u32(data)
    pl, loc, seq, pos = client.unpack_location(loc)
    type = client.read_u8(data)
    value = client.read_u32(data)
    card = client.get_card(pl, loc, seq)
    if card:
        card_hint(client, card, type, value)
    return data.read()


def card_hint(client, card, type, value):
    if type == 3: # race announcement
        races = [variables.LANGUAGE_HANDLER.strings['system'][card_constants.RACES_OFFSET +i] for i in range(card_constants.AMOUNT_RACES) if value & (1<<i)]
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("{spec} ({name}) selected {value}.").format(spec=card.get_name(), name=card.get_name(), value=', '.join(races))))
    elif type == 4: # attribute announcement
        attributes = [variables.LANGUAGE_HANDLER.strings['system'][card_constants.ATTRIBUTES_OFFSET+i] for i in range(card_constants.AMOUNT_ATTRIBUTES) if value & (1<<i)]
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("{spec} ({name}) selected {value}.").format(spec=card.get_name(), name=card.get_name(), value=', '.join(attributes))))

    else:
        logger.debug(f"unhandled card hint type {type}, value {value}")

# MESSAGES = {160: msg_card_hint}
