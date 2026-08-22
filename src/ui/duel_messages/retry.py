import logging

from core import utils
from core.i18n import _

logger = logging.getLogger(__name__)


@utils.duel_message_handler(1)
def msg_retry(client, data, data_length):
    logger.warning("Server requested retry — previous response was invalid")
    utils.output(_("Invalid response. Please try again."))
