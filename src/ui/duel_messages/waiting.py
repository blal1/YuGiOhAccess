import io
import logging

from core import utils
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_WAITING)
def msg_waiting(client, data, length):
    data = io.BytesIO(data[1:])
    return waiting(client, data)

def waiting(client, data):
    logger.debug("Waiting for something to happen.")
