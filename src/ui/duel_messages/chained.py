"""MSG_CHAINED and friends: how the chain resolves.

Building the chain is announced by ``chaining.py``. These messages report what
happens to it afterwards, which used to be debug logging only: the player heard
cards being chained and then silence, with no way to tell which link resolved,
which was negated, or when the chain finished.

Every one of these carries a single u8: the chain link the message is about.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_CHAINED)
def msg_chained(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    chained(client, count)


@utils.duel_message_handler(message_constants.MSG_CHAIN_SOLVING)
def msg_chain_solving(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    chain_solving(client, count)


@utils.duel_message_handler(message_constants.MSG_CHAIN_END)
def msg_chain_end(client, data, data_length):
    chain_end(client)


@utils.duel_message_handler(message_constants.MSG_CHAIN_SOLVED)
def msg_chain_solved(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    chain_solved(client, count)


@utils.duel_message_handler(message_constants.MSG_CHAIN_NEGATED)
def msg_chain_negated(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    chain_negated(client, count)


@utils.duel_message_handler(message_constants.MSG_CHAIN_DISABLED)
def msg_chain_disabled(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u8(data)
    chain_disabled(client, count)


def _link_name(client, link):
    """Name of the card at ``link`` (1 based) on the chain, if it is known."""
    player = getattr(client, "player", None)
    stack = getattr(player, "chain_stack", None) if player else None
    if not isinstance(stack, list) or not stack or link < 1 or link > len(stack):
        return ""
    return stack[link - 1].get_name()


def _describe(client, link, with_name, without_name):
    name = _link_name(client, link)
    if name:
        return with_name.format(link=link, name=name)
    return without_name.format(link=link)


def chained(client, count):
    logger.debug("Chain link %s added", count)


def chain_solving(client, count):
    utils.output(
        _describe(
            client, count,
            _("Resolving chain link {link}, {name}."),
            _("Resolving chain link {link}."),
        ),
        priority=speech.Priority.INFO,
    )


def chain_solved(client, count):
    logger.debug("Chain link %s solved", count)


def chain_negated(client, count):
    utils.output(
        _describe(
            client, count,
            _("Chain link {link}, {name}, was negated."),
            _("Chain link {link} was negated."),
        ),
        priority=speech.Priority.CRITICAL,
    )


def chain_disabled(client, count):
    utils.output(
        _describe(
            client, count,
            _("The effect of chain link {link}, {name}, was disabled."),
            _("The effect of chain link {link} was disabled."),
        ),
        priority=speech.Priority.CRITICAL,
    )


def chain_end(client):
    player = getattr(client, "player", None)
    if player is None:
        return
    stack = getattr(player, "chain_stack", None)
    depth = len(stack) if isinstance(stack, list) else 0
    player.chaining_cards = []
    player.chain_stack = []
    if depth > 1:
        utils.output(
            _("Chain of {depth} finished resolving.").format(depth=depth),
            priority=speech.Priority.INFO,
        )
