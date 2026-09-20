"""MSG_SWAP_GRAVE_DECK: a player's deck and graveyard traded places.

Cards the player had memorised in the graveyard are now in the deck and vice
versa, so this has to be announced loudly and the browsable graveyard zones have
to be dropped; the refresh that follows repopulates them.

Wire format:

    u8 player
    u32 number of extra deck monsters that were pulled out of the graveyard
    u32 length of the bitmap that marks which of them they were
    the bitmap itself
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_SWAP_GRAVE_DECK)
def msg_swap_grave_deck(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    returned_to_extra = client.read_u32(data)
    bitmap_length = client.read_u32(data)
    bitmap = data.read(bitmap_length)
    logger.debug(
        "Swap grave/deck: player=%s, returned to extra=%s, bitmap=%s bytes",
        player, returned_to_extra, len(bitmap),
    )
    swap_grave_deck(client, player, returned_to_extra)


def swap_grave_deck(client, player, returned_to_extra=0):
    field = client.get_duel_field()
    if field:
        # Every graveyard position the player memorised is now wrong.
        if player == client.what_player_am_i:
            field.clear_player_graveyard()
        else:
            field.clear_opponent_graveyard()
    if player == client.what_player_am_i:
        message = _("Your deck and graveyard were swapped.")
    else:
        message = _("Your opponent's deck and graveyard were swapped.")
    if returned_to_extra:
        message = _("{message} {count} extra deck monster(s) went back to the extra deck.").format(
            message=message, count=returned_to_extra
        )
    utils.output(message, priority=speech.Priority.CRITICAL)
    utils.get_ui_stack().play_duel_sound_effect("shuffle")
