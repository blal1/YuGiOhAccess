import io
import logging

from core import utils

logger = logging.getLogger(__name__)

@utils.duel_message_handler(3)
def msg_waiting(client, data, length):
    data = io.BytesIO(data[1:])
    return waiting(client, data)

def waiting(client, data):
    logger.debug("Waiting for something to happen.")
