import io
import logging

from core import utils
from core.i18n import _
from game.card.card import Card

logger = logging.getLogger(__name__)


@utils.duel_message_handler(8)
def msg_shuffle_hand(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    codes = []
    for i in range(count):
        codes.append(client.read_u32(data))
    logger.debug(f"Shuffle hand: player={player}, count={count}")
    if player == client.what_player_am_i:
        utils.output(_("Your hand was shuffled."))
    else:
        utils.output(_("Your opponent's hand was shuffled."))


@utils.duel_message_handler(9)
def msg_shuffle_extra(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    logger.debug(f"Shuffle extra: player={player}, count={count}")
    if player == client.what_player_am_i:
        utils.output(_("Your extra deck was shuffled."))
    else:
        utils.output(_("Your opponent's extra deck was shuffled."))
