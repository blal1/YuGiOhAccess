"""MSG_RETRY: the core rejected our answer and wants another one.

The duel is still blocked on the same question. Saying "invalid response" and
stopping there left the player with nothing on screen to answer and no way to
get the question back, so the duel simply stalled: the only way on was to
surrender or close the client.

The question the client last displayed is kept by ``ui.remember_prompt``, and
putting it back on screen is what EDOPro does here too.
"""

import logging

import wx

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants, message_routing

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_RETRY)
def msg_retry(client, data, data_length):
    logger.warning("Server requested retry — previous response was invalid")
    prompt = getattr(getattr(client, "memory", None), "last_prompt", None)
    if not prompt:
        # Nothing to put back. Say so plainly: the duel is waiting on an
        # answer the player cannot give, and silence would be worse.
        logger.error("MSG_RETRY arrived with no prompt to repeat")
        utils.output(
            _("The duel rejected that answer, and the question could not be shown again."),
            priority=speech.Priority.CRITICAL,
        )
        return

    duel_message_id, packet_data, packet_length = prompt
    handler = utils.duel_message_handlers.get(duel_message_id)
    if handler is None:
        logger.error("No handler to repeat duel message %s with", duel_message_id)
        utils.output(
            _("The duel rejected that answer, and the question could not be shown again."),
            priority=speech.Priority.CRITICAL,
        )
        return

    utils.output(
        _("That answer was not allowed. Asking again: {prompt}").format(
            prompt=message_routing.message_name(duel_message_id)
        ),
        priority=speech.Priority.CRITICAL,
    )
    # Rebuilt on the next turn of the event loop, for the same reason the
    # first one was: the handler pushes a screen, and doing that from inside
    # another message's handler is what strands prompts behind each other.
    wx.CallAfter(handler, client, packet_data, packet_length)
