import io
import logging

from core import utils

logger = logging.getLogger(__name__)


@utils.duel_message_handler(71)
@utils.duel_message_handler(72)
def msg_chained(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    # print the rest of the data if there is any
    logger.debug(data.read())
    chained(client, count)

@utils.duel_message_handler(74)
def msg_chain_end(client, data, data_length):
    return # it seems that this message is empty

@utils.duel_message_handler(73)
def msg_chain_solved(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    logger.debug(data.read())
    chain_solved(client, count)

@utils.duel_message_handler(75)
def msg_chain_negated(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    # print the rest of the data if there is any
    logger.debug(data.read())
    chain_negated(client, count)

@utils.duel_message_handler(76)
def msg_chain_disabled(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    # print the rest of the data if there is any
    logger.debug(data.read())
    chain_disabled(client, count)
    


def chained(client, count):
    logger.debug(f"Chained with {count} cards")

def chain_negated(client, count):
    logger.debug(f"Chain negated with {count} cards")

def chain_disabled(client, count):
    logger.debug(f"Chain disabled with {count} cards")

def chain_solved(client, count):
    logger.debug(f"Chain solved with {count} cards")
    if getattr(client, "player", None):
        client.player.chaining_cards = []
