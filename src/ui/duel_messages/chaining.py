"""MSG_CHAINING: a card is being added to the chain.

A sighted player watches the chain build on screen, so they always know how deep
it is and what each link is answering. This handler keeps the same information
available by ear: every link is announced with its number and, from link two
onwards, the link it is responding to. The running stack is kept on the player
so the C key can read it back at any time (see ``DuelField.get_chain_stack_text``).

Wire format: u32 code, loc_info, u8 triggering controller, u8 triggering
location, u32 triggering sequence, u64 effect description, u32 chain size.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_CHAINING)
def msg_chaining(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    controller, location, sequence, position = client.read_location(data)
    card = Card(code)
    card.set_location_and_position_info(controller, location, sequence, position)
    tc = client.read_u8(data)
    tl = client.read_u8(data)
    ts = client.read_u32(data)
    desc = client.read_u64(data)
    cs = client.read_u32(data)
    chaining(client, card, tc, tl, ts, desc, cs)


def chaining(client, card, triggering_controller, triggering_location, triggering_sequence, desc, chaining_size):
    card.effect_description = card.get_effect_description(desc, True)
    card.chain_link = chaining_size
    stack = _chain_stack(client)
    if stack is not None:
        # A new chain starts over at link 1; the core counts from 1 upwards.
        if chaining_size <= 1:
            del stack[:]
        stack.append(card)
    if card.controller == client.what_player_am_i:
        who = _("You activate")
    else:
        who = _("Your opponent activates")
    parts = [
        _("Chain link {link}: {who} {name}.").format(
            link=max(chaining_size, 1), who=who, name=card.get_name()
        )
    ]
    responding_to = _responding_to(stack, chaining_size)
    if responding_to:
        parts.append(_("Responding to {name}.").format(name=responding_to.get_name()))
    if card.effect_description:
        parts.append(card.effect_description)
    utils.output(" ".join(parts), priority=speech.Priority.CRITICAL)


def _chain_stack(client):
    player = getattr(client, "player", None)
    if player is None:
        return None
    stack = getattr(player, "chain_stack", None)
    if not isinstance(stack, list):
        player.chain_stack = stack = []
    return stack


def _responding_to(stack, chaining_size):
    """The link this one is answering: the previous entry on the stack."""
    if not stack or chaining_size <= 1 or len(stack) < 2:
        return None
    return stack[-2]


def chain_stack_text(client):
    """Readable description of the chain as it currently stands."""
    stack = _chain_stack(client)
    if not stack:
        return _("No chain is currently building.")
    lines = [_("Chain of {depth}:").format(depth=len(stack))]
    for index, card in enumerate(stack, start=1):
        owner = _("you") if card.controller == client.what_player_am_i else _("your opponent")
        description = getattr(card, "effect_description", "")
        if description:
            lines.append(
                _("{index}: {name} by {owner}, {description}").format(
                    index=index, name=card.get_name(), owner=owner, description=description
                )
            )
        else:
            lines.append(
                _("{index}: {name} by {owner}").format(index=index, name=card.get_name(), owner=owner)
            )
    return "\n".join(lines)
