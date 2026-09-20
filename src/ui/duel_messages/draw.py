import io
import logging
import threading
import time

from core import exceptions
from core import dotdict
from core import utils
from core.i18n import _

from game.card import card_constants
from game.card.card import Card
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_DRAW)
def msg_draw(client, data, length):
    data = io.BytesIO(data[1:])
    # print out the rest of the data
    player = client.read_u8(data)
    drawed = client.read_u32(data)
    cards = []
    for i in range(drawed):
        code = client.read_u32(data)
        position = client.read_u32(data)
        try:
            card = Card(code)
            card.set_location_and_position_info(player, card_constants.LOCATION.HAND, i, position)
            cards.append(card)
        except exceptions.CardNotFoundException:
            cards.append(None)
    draw(client, player, cards)

def draw(client, player, cards):
    sync_drawn_cards(client, player, cards)
    _player = _("You") if client.what_player_am_i == player else _("Your opponent")
    utils.output(_("{player} drew {count} cards").format(player=_player, count=len(cards)))
    # if all of the cards are None
    if all(card is None for card in cards):
        return
    # if all cards are some form of face down, don't print them
    if all(not card.get_name()for card in cards):
        return
    threading.Thread(target=_play_draw_sound_effect, args=(len(cards),)).start()
    for x in range(len(cards)):
        if cards[x] is not None:
            logger.debug(f"Drew card code: {cards[x].code}")
            utils.output(_("{n}: {name}.").format(n=x+1, name=cards[x].get_name()))
        else:
            utils.output(_("{n}: face down.").format(n=x))

def _play_draw_sound_effect(amount):
    for i in range(amount):
        try:
            utils.get_ui_stack().play_random_duel_sound_effect_in_directory("draw")
        except Exception:
            logger.debug("Skipping draw sound effect because the UI stack is unavailable", exc_info=True)
            return
        time.sleep(0.2)


def sync_drawn_cards(client, player, cards):
    get_duel_field = getattr(client, "get_duel_field", None)
    if get_duel_field is None:
        return
    field = get_duel_field()
    if field is None:
        return
    if not all(hasattr(field, attr) for attr in ("get_subset_of_zones", "append_card_to_player_hand", "append_card_to_opponent_hand")):
        return
    is_player = player == client.what_player_am_i
    for card in cards:
        if card is None:
            if not is_player:
                query = _hand_query(player, len(field.get_subset_of_zones("oh")), 0)
                field.append_card_to_opponent_hand(_("Face down card"), query)
            continue
        if is_player:
            sequence = len(field.get_subset_of_zones("ph"))
            card.set_location_and_position_info(player, card_constants.LOCATION.HAND, sequence, card.position)
            field.append_card_to_player_hand(card)
        else:
            sequence = len(field.get_subset_of_zones("oh"))
            card.set_location_and_position_info(player, card_constants.LOCATION.HAND, sequence, card.position)
            field.append_card_to_opponent_hand(card, _hand_query(player, sequence, card.position))


def _hand_query(player, sequence, position):
    query = dotdict.DotDict()
    query.controller = player
    query.location = card_constants.LOCATION.HAND
    query.sequence = sequence
    query.position = position
    return query
