"""Message ids ocgcore declares but the bundled core never sends.

Older cores and some third party servers still emit them. Registering handlers
here costs nothing and keeps two things from happening: the client logging
"Unhandled duel message id" for a message that is perfectly normal, and a future
handler being wired onto one of these ids by mistake.

Anything with player facing meaning is announced; the pure bookkeeping ones are
logged at debug level and dropped.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_UNEQUIP)
def msg_unequip(client, data, data_length):
    """A card stopped being equipped to its target. Payload: loc_info."""
    data = io.BytesIO(data[1:])
    controller, location, sequence, _position = client.read_location(data)
    card = client.get_card(controller, location, sequence)
    name = card.get_name() if card else _("A card")
    utils.output(_("{name} is no longer equipped.").format(name=name), priority=speech.Priority.INFO)


@utils.duel_message_handler(message_constants.MSG_BE_CHAIN_TARGET)
def msg_be_chain_target(client, data, data_length):
    """One of the player's cards became the target of a chain link.

    The bundled core folds this into MSG_BECOME_TARGET and never sends it, and
    the cores that do send it send no payload.
    """
    utils.output(_("One of your cards became a chain target."), priority=speech.Priority.CRITICAL)


@utils.duel_message_handler(message_constants.MSG_CREATE_RELATION)
@utils.duel_message_handler(message_constants.MSG_RELEASE_RELATION)
def msg_relation(client, data, data_length):
    """Internal card-to-card bookkeeping. Nothing a player can act on."""
    logger.debug("Ignoring relation message %s", data[:1])


@utils.duel_message_handler(message_constants.MSG_REQUEST_DECK)
@utils.duel_message_handler(message_constants.MSG_REFRESH_DECK)
def msg_deck_bookkeeping(client, data, data_length):
    """Deck plumbing between core and server; the client sees the result instead."""
    logger.debug("Ignoring deck bookkeeping message %s", data[:1])


@utils.duel_message_handler(message_constants.MSG_CUSTOM_MSG)
def msg_custom(client, data, data_length):
    """Server defined payload. Logged so custom servers can be diagnosed."""
    logger.debug("Custom duel message, %s bytes: %r", data_length, data[1:])
