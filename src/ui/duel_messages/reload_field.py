"""MSG_RELOAD_FIELD: full field resynchronisation.

The core sends this after a reconnect, when a spectator joins mid duel, and
after a rejoin. Without a handler the field the player memorised stays frozen at
whatever it was before the interruption, so every zone they tab to afterwards is
a lie. Here we drop the stale field, announce the counts that came with the
resync, and let the MSG_UPDATE_DATA burst that follows repopulate the zones.

Wire format (field::reload_field_info):

    u32 duel_options
    for each of the two players:
        u32 life points
        7 x monster zone slot
        8 x spell/trap zone slot
        u32 main deck, hand, graveyard, banished, extra deck, extra pendulum
    u32 chain size
    chain size x (u32 code, loc_info, u8 controller, u8 location,
                  u32 sequence, u64 description)

A zone slot is a single 0 byte when empty, or 1 followed by u8 position and
u32 overlay count.
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import message_constants

logger = logging.getLogger(__name__)

MONSTER_ZONE_COUNT = 7
SPELL_AND_TRAP_ZONE_COUNT = 8


class FieldSide:
    """The counts the core reports for one player."""

    def __init__(self):
        self.lifepoints = 0
        self.monsters = []
        self.spells_and_traps = []
        self.deck = 0
        self.hand = 0
        self.graveyard = 0
        self.banished = 0
        self.extra_deck = 0
        self.extra_pendulum = 0

    @property
    def monster_count(self):
        return len(self.monsters)

    @property
    def spell_and_trap_count(self):
        return len(self.spells_and_traps)


@utils.duel_message_handler(message_constants.MSG_RELOAD_FIELD)
def msg_reload_field(client, data, data_length):
    data = io.BytesIO(data[1:])
    duel_options = client.read_u32(data)
    sides = [_read_side(client, data), _read_side(client, data)]
    chain = _read_chain(client, data)
    logger.debug("Reload field: duel options=%s, chain depth=%s", duel_options, len(chain))
    reload_field(client, sides, chain)


def _read_zone_slots(client, data, count):
    """Read ``count`` zone slots, returning the occupied ones."""
    occupied = []
    for sequence in range(count):
        if not client.read_u8(data):
            continue
        position = client.read_u8(data)
        overlay_count = client.read_u32(data)
        occupied.append((sequence, position, overlay_count))
    return occupied


def _read_side(client, data):
    side = FieldSide()
    side.lifepoints = client.read_u32(data)
    side.monsters = _read_zone_slots(client, data, MONSTER_ZONE_COUNT)
    side.spells_and_traps = _read_zone_slots(client, data, SPELL_AND_TRAP_ZONE_COUNT)
    side.deck = client.read_u32(data)
    side.hand = client.read_u32(data)
    side.graveyard = client.read_u32(data)
    side.banished = client.read_u32(data)
    side.extra_deck = client.read_u32(data)
    side.extra_pendulum = client.read_u32(data)
    return side


def _read_chain(client, data):
    chain = []
    size = client.read_u32(data)
    for _unused in range(size):
        code = client.read_u32(data)
        controller, location, sequence, position = client.read_location(data)
        card = Card(code)
        card.set_location_and_position_info(controller, location, sequence, position)
        triggering_controller = client.read_u8(data)
        triggering_location = client.read_u8(data)
        triggering_sequence = client.read_u32(data)
        description = client.read_u64(data)
        card.effect_description = card.get_effect_description(description, True)
        logger.debug(
            "Reloaded chain link: %s triggered from %s/%s/%s",
            code, triggering_controller, triggering_location, triggering_sequence,
        )
        chain.append(card)
    return chain


def reload_field(client, sides, chain):
    field = client.get_duel_field()
    if field:
        field.reset_field()
    _update_lifepoints(client, sides)
    player = getattr(client, "player", None)
    if player is not None:
        # This is the chain that is actually resolving, so it belongs on the
        # chain stack; the list of cards we could chain with is gone.
        player.chain_stack = list(chain)
        player.chaining_cards = []
    utils.output(describe_reload(client, sides, chain), priority=speech.Priority.CRITICAL)


def _update_lifepoints(client, sides):
    player = getattr(client, "player", None)
    if player is None:
        return
    you = client.what_player_am_i if client.what_player_am_i in (0, 1) else 0
    player.update_lifepoints(sides[you].lifepoints)
    player.update_lifepoints(sides[1 - you].lifepoints, True)


def describe_reload(client, sides, chain):
    you = client.what_player_am_i if client.what_player_am_i in (0, 1) else 0
    mine, theirs = sides[you], sides[1 - you]
    lines = [_("Field resynchronised.")]
    lines.append(
        _(
            "You: {lp} life points, {hand} in hand, {monsters} monsters, "
            "{spells} spells or traps, {deck} in deck, {grave} in graveyard, "
            "{banished} banished, {extra} in extra deck."
        ).format(
            lp=mine.lifepoints,
            hand=mine.hand,
            monsters=mine.monster_count,
            spells=mine.spell_and_trap_count,
            deck=mine.deck,
            grave=mine.graveyard,
            banished=mine.banished,
            extra=mine.extra_deck,
        )
    )
    lines.append(
        _(
            "Opponent: {lp} life points, {hand} in hand, {monsters} monsters, "
            "{spells} spells or traps, {deck} in deck, {grave} in graveyard, "
            "{banished} banished, {extra} in extra deck."
        ).format(
            lp=theirs.lifepoints,
            hand=theirs.hand,
            monsters=theirs.monster_count,
            spells=theirs.spell_and_trap_count,
            deck=theirs.deck,
            grave=theirs.graveyard,
            banished=theirs.banished,
            extra=theirs.extra_deck,
        )
    )
    if chain:
        lines.append(_("Chain of {depth} still resolving.").format(depth=len(chain)))
        for index, card in enumerate(chain, start=1):
            lines.append(_("{index}: {name}").format(index=index, name=card.get_name()))
    return "\n".join(lines)
