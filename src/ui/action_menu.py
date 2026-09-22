import logging
import struct

from ui.base_ui import VerticalMenu
from core import speech
from core import utils
from core.i18n import _

from game.edo import structs
from game.card.card import Card
from ui import playable_cards

logger = logging.getLogger(__name__)

def show_action_menu_for_zone(client, zone):
    if not isinstance(zone.card, Card):
        return
    # Everything below describes the duel as it stands right now. Remember when
    # that was, so an activation seconds later can tell whether it still holds.
    generation = getattr(client.player, "state_generation", None)
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
        action_menu.append_item(_("Attack"), function=lambda: send_attack(client, zone.card, generation=generation))
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
            action_menu.append_item(_("Activate effect: {desc}").format(desc=effect_descriptions[0]), function=lambda: send_activate(client, zone.card, generation=generation))
        else:
            for i in range(activate_count):
                action_menu.append_item(_("Activate effect {n}: {desc}").format(n=i+1, desc=effect_descriptions[i]), function=lambda i=i: send_activate(client, zone.card, i, generation=generation))
    if special_summonable:
        action_menu.append_item(_("Special summon"), function=lambda: send_special_summon(client, zone.card, generation=generation))
    if summonable:
        action_menu.append_item(_("Summon"), function=lambda: send_summon(client, zone.card, generation=generation))
    if monster_settable:
        action_menu.append_item(_("Set"), function=lambda: send_monster_set(client, zone.card, generation=generation))
    if spell_settable:
        action_menu.append_item(_("Set"), function=lambda: send_spell_set(client, zone.card, generation=generation))
    if repositionable:
        action_menu.append_item(_("Reposition"), function=lambda: send_reposition(client, zone.card, generation=generation))
    action_menu.append_cancel_item(_("Close"), utils.get_ui_stack().pop_ui)
    utils.get_ui_stack().push_ui(action_menu)

def _resolve_action(client, cards, card, addition=0, generation=None):
    """The index to send for this action, or None if it is no longer offered.

    Two ways a menu goes out of date: the duel asked a new question and threw
    the old lists away, or this particular action simply is not in the list any
    more. Either way the answer is to say so, not to send an index that now
    means something else.
    """
    current = getattr(client.player, "state_generation", None)
    if generation is not None and current is not None and current != generation:
        logger.info("Refusing an action from a menu that predates the current prompt")
        utils.output(
            _("That action is no longer available; the duel has moved on."),
            priority=speech.Priority.CRITICAL,
        )
        return None
    try:
        return playable_cards.first_matching_index(cards, card, addition)
    except ValueError:
        logger.warning(
            "Action for %s is not available any more (%d option(s), wanted %s)",
            getattr(card, "code", "?"), len(cards), addition,
        )
        utils.output(
            _("That action is no longer available."),
            priority=speech.Priority.CRITICAL,
        )
        return None


def _send_action(client, cards, card, response, addition=0, generation=None):
    utils.get_ui_stack().pop_ui()
    index = _resolve_action(client, cards, card, addition, generation)
    if index is None:
        return
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', (index << 16) + response))


def send_activate(client, card, addition=0, generation=None):
    logger.debug(f"Length of activatable: {len(client.player.activatable)}")
    logger.debug(f"Tried action addition: {addition}")
    _send_action(client, client.player.activatable, card, 5, addition, generation)


def send_attack(client, card, generation=None):
    _send_action(client, client.player.attackable, card, 1, generation=generation)


def send_special_summon(client, card, generation=None):
    _send_action(client, client.player.special_summonable, card, 1, generation=generation)


def send_summon(client, card, generation=None):
    _send_action(client, client.player.summonable, card, 0, generation=generation)


def send_monster_set(client, card, generation=None):
    _send_action(client, client.player.monster_settable, card, 3, generation=generation)


def send_spell_set(client, card, generation=None):
    _send_action(client, client.player.spell_settable, card, 4, generation=generation)


def send_reposition(client, card, generation=None):
    _send_action(client, client.player.repositionable, card, 2, generation=generation)
