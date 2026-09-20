import io
import logging
from enum import IntFlag
from core import utils
from core import variables
from game.edo import message_constants

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



@utils.duel_message_handler(message_constants.MSG_HINT)
def msg_hint(client, data, length):
    data = io.BytesIO(data[1:])
    htype = client.read_u8(data)
    hint_type = HINT(htype)
    player = client.read_u8(data)
    value = client.read_u64(data)
    return hint(client, hint_type, player, value)

def hint(client, hint_type, player, data):
    if hint_type == HINT.MESSAGE:
        utils.output(str(data))
    elif hint_type == HINT.NUMBER:
        utils.output(variables.LANGUAGE_HANDLER.strings['system'][1512] % data)
    else:
        logger.debug(f"Hint type: {hint_type}, player: {player}, data: {data}")
