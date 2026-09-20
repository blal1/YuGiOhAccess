"""MSG_MATCH_KILL: a card ended the whole match, not just the duel.

Only a handful of cards do this (Victory Dragon and friends). Without the
announcement the player hears the duel end with no explanation of why there is
no game two.

Wire format: u32 card code.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_MATCH_KILL)
def msg_match_kill(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    match_kill(client, Card(code))


def match_kill(client, card):
    logger.debug("Match kill by %s", card.code)
    utils.output(
        _("{name} ended the entire match.").format(name=card.get_name()),
        priority=speech.Priority.CRITICAL,
    )
