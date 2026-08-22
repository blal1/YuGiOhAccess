import io
import logging

from core import utils

from game.card.card import Card
from ui import playable_cards

logger = logging.getLogger(__name__)

@utils.duel_message_handler(11)
def msg_idlecmd(client, data, length):
    logger.debug("Idle command")
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    if player != client.what_player_am_i:
        return # todo implement this
    logger.debug("reading summonable")
    summonable = client.read_cardlist(data)
    logger.debug("reading spsummon")
    spsummon = client.read_cardlist(data)
    logger.debug("reading repos")
    repos = client.read_cardlist(data, sequence_size=8)
    logger.debug("reading idle_mset")
    idle_mset = client.read_cardlist(data)
    logger.debug("reading idle_set")
    idle_set = client.read_cardlist(data)
    logger.debug("reading idle_activate")
    idle_activate = client.read_cardlist(data, True)
    logger.debug("reading to_bp")
    to_bp = client.read_u8(data)
    logger.debug("reading to_ep")
    to_ep = client.read_u8(data)
    logger.debug("reading can_shuffle")
    can_shuffle = client.read_u8(data)
    client.player.clear_all()
    client.player.summonable = summonable
    client.player.special_summonable = spsummon
    client.player.repositionable = repos
    client.player.monster_settable = idle_mset
    client.player.spell_settable = idle_set
    client.player.activatable = idle_activate
    client.player.can_go_to_battle_phase = to_bp
    client.player.can_go_to_end_phase = to_ep
    client.player.can_shuffle = can_shuffle
    return idle(client, player)

def idle(client, player_id):
    # make a super set, of all the lists
    all_cards = client.player.summonable + client.player.special_summonable + client.player.repositionable + client.player.monster_settable + client.player.spell_settable + client.player.activatable
    if not all_cards:
        client.get_duel_field().tab_order.set_tabable_items([])
        return
    updated_tab_order = playable_cards.playable_zone_keys(client.get_duel_field().zones, all_cards, Card)
    client.get_duel_field().tab_order.set_tabable_items(updated_tab_order)
