"""MSG_TAG_SWAP: a tag duel partner takes over.

Everything the player knew about that side's hand, deck and extra deck is
replaced at once. Without this message tag duels cannot be played at all: the
field would keep describing the partner who just left.

Wire format:

    u8 player
    u32 main deck size
    u32 extra deck size
    u32 extra deck pendulum count
    u32 hand size
    u32 revealed top deck card code (0 unless the deck is reversed)
    hand size  x (u32 code, u32 position)
    extra size x (u32 code, u32 position)
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.card.card import Card
from game.card import card_constants
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_TAG_SWAP)
def msg_tag_swap(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    deck_size = client.read_u32(data)
    extra_size = client.read_u32(data)
    extra_pendulum_count = client.read_u32(data)
    hand_size = client.read_u32(data)
    top_deck_code = client.read_u32(data)
    hand = _read_cards(client, data, hand_size, player, card_constants.LOCATION.HAND)
    extra = _read_cards(client, data, extra_size, player, card_constants.LOCATION.EXTRA)
    logger.debug(
        "Tag swap: player=%s deck=%s extra=%s hand=%s", player, deck_size, extra_size, hand_size
    )
    tag_swap(client, player, deck_size, extra, extra_pendulum_count, hand, top_deck_code)


def _read_cards(client, data, count, controller, location):
    cards = []
    for sequence in range(count):
        code = client.read_u32(data)
        position = client.read_u32(data)
        card = Card(code)
        try:
            card.set_location_and_position_info(
                controller, location, sequence, card_constants.POSITION(position)
            )
        except ValueError:
            logger.debug("Unknown position %s in tag swap", position)
        cards.append(card)
    return cards


def tag_swap(client, player, deck_size, extra, extra_pendulum_count, hand, top_deck_code=0):
    field = client.get_duel_field()
    is_yours = player == client.what_player_am_i
    if field:
        # The partner's hand and extra deck replace the ones on the field.
        if is_yours:
            field.clear_player_hand()
            field.clear_player_extra_deck()
            for card in hand:
                field.append_card_to_player_hand(card)
        else:
            field.clear_opponent_hand()
            field.clear_opponent_extra_deck()
    lines = []
    if is_yours:
        lines.append(_("Your tag partner takes over."))
    else:
        lines.append(_("Your opponent's tag partner takes over."))
    lines.append(
        _("{hand} card(s) in hand, {deck} in deck, {extra} in extra deck.").format(
            hand=len(hand), deck=deck_size, extra=len(extra)
        )
    )
    if is_yours and hand:
        lines.append(_("Your new hand: {cards}").format(cards=", ".join(card.get_name() for card in hand)))
    if top_deck_code:
        lines.append(_("Top of deck: {name}").format(name=Card(top_deck_code).get_name()))
    utils.output("\n".join(lines), priority=speech.Priority.CRITICAL)
