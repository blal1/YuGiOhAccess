import logging
import struct

from ui.base_ui import VerticalMenu
from core import utils
from core.i18n import _

from game.edo import structs
from game.card.card import Card
from ui import playable_cards

logger = logging.getLogger(__name__)

def show_action_menu_for_zone(client, zone):
    if not isinstance(zone.card, Card):
        return
    attackable = playable_cards.matching_cards(zone.card, client.player.attackable)
    activatable = playable_cards.matching_cards(zone.card, client.player.activatable)
    special_summonable = playable_cards.matching_cards(zone.card, client.player.special_summonable)
    summonable = playable_cards.matching_cards(zone.card, client.player.summonable)
    monster_settable = playable_cards.matching_cards(zone.card, client.player.monster_settable)
    spell_settable = playable_cards.matching_cards(zone.card, client.player.spell_settable)
    repositionable = playable_cards.matching_cards(zone.card, client.player.repositionable)
    if not any((attackable, activatable, special_summonable, summonable, monster_settable, spell_settable, repositionable)):
        utils.output(_("No available action for {card}.").format(card=zone.card.get_name()))
        return
    action_menu = VerticalMenu(_("Action Menu"))
    action_menu.append_item(_("Actions for {card}").format(card=zone.card.get_name()))
    if attackable:
        action_menu.append_item(_("Attack"), function=lambda: send_attack(client, zone.card))
    activate_count = len(activatable)
    if activate_count > 0:
        effect_descriptions = []
        for i in range(1, activate_count):
            description = zone.card.strings[i]
            effect_descriptions.append(description)
        ind = activatable[0].data
        effect_card = activatable[0]
        get_effect_description = getattr(effect_card, "get_effect_description", None)
        if get_effect_description is None:
            get_effect_description = getattr(zone.card, "get_effect_description")
        description = get_effect_description(ind)
        effect_descriptions.append(description)
        if activate_count == 1:
            action_menu.append_item(_("Activate effect: {desc}").format(desc=effect_descriptions[0]), function=lambda: send_activate(client, zone.card))
        else:
            for i in range(activate_count):
                action_menu.append_item(_("Activate effect {n}: {desc}").format(n=i+1, desc=effect_descriptions[i]), function=lambda i=i: send_activate(client, zone.card, i))
    if special_summonable:
        action_menu.append_item(_("Special summon"), function=lambda: send_special_summon(client, zone.card))
    if summonable:
        action_menu.append_item(_("Summon"), function=lambda: send_summon(client, zone.card))
    if monster_settable:
        action_menu.append_item(_("Set"), function=lambda: send_monster_set(client, zone.card))
    if spell_settable:
        action_menu.append_item(_("Set"), function=lambda: send_spell_set(client, zone.card))
    if repositionable:
        action_menu.append_item(_("Reposition"), function=lambda: send_reposition(client, zone.card))
    action_menu.append_item(_("Close"), utils.get_ui_stack().pop_ui)
    utils.get_ui_stack().push_ui(action_menu)

def send_activate(client, card, addition=0):
    utils.get_ui_stack().pop_ui()
    logger.debug(f"Length of activatable: {len(client.player.activatable)}")
    logger.debug(f"Tried action addition: {addition}")
    index = playable_cards.first_matching_index(client.player.activatable, card, addition)
    logger.debug(f"Activating effect {index}")
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16)+5))


def send_attack(client, card):
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.attackable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16)+1))

def send_special_summon(client, card):
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.special_summonable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16)+1))

def send_summon(client, card):
    # list all uis in the stack
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.summonable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', index << 16))

def send_monster_set(client, card):
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.monster_settable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16) + 3))
        
def send_spell_set(client, card):
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.spell_settable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16) + 4))

def send_reposition(client, card):
    utils.get_ui_stack().pop_ui()
    index = playable_cards.first_matching_index(client.player.repositionable, card)
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16) + 2))
        
