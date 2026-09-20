import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_RETRY)
def msg_retry(client, data, data_length):
    logger.warning("Server requested retry — previous response was invalid")
    utils.output(_("Invalid response. Please try again."), priority=speech.Priority.CRITICAL)
