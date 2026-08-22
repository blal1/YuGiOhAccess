import io
import logging

from core import utils
from core.i18n import _

logger = logging.getLogger(__name__)


@utils.duel_message_handler(34)
def msg_shuffle_set_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    location = client.read_u8(data)
    count = client.read_u8(data)
    logger.debug(f"Shuffle set cards: location={location}, count={count}")
    utils.output(_("Set cards on the field were shuffled."))
