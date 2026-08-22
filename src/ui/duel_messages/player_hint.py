import io
import logging

from core import utils

logger = logging.getLogger(__name__)


@utils.duel_message_handler(82)
def msg_player_hint(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    hint_type = client.read_u8(data)
    value = client.read_u64(data)
    logger.debug(f"Player hint: player={player}, type={hint_type}, value={value}")
