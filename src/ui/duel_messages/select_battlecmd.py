import io

from game.card.card import Card
from core import utils
from ui import playable_cards
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_SELECT_BATTLECMD)
def msg_select_battlecmd(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    activatable = client.read_cardlist(data, True)
    attackable = client.read_cardlist(data, True, True, 8)
    to_m2 = client.read_u8(data)
    to_ep = client.read_u8(data)
    client.player.clear_all()
    client.player.activatable = activatable
    client.player.attackable = attackable
    client.player.can_go_to_main_phase2 = to_m2
    client.player.can_go_to_end_phase = to_ep
    select_battlecmd(client, player, activatable, attackable, to_m2, to_ep)

def select_battlecmd(client, player, activatable, attackable, to_m2, to_ep):
    display_battle_menu(client)

def display_battle_menu(client):
    # make a super set, of all the lists
    all_cards = client.player.activatable + client.player.attackable
    if not all_cards:
        client.get_duel_field().tab_order.set_tabable_items([])
        return
    updated_tab_order = playable_cards.playable_zone_keys(client.get_duel_field().zones, all_cards, Card)
    client.get_duel_field().tab_order.set_tabable_items(updated_tab_order)
