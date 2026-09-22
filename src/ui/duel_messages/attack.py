import io

from game.card.card import Card
from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_ATTACK)
def msg_attack(client, data, data_length):
    data = io.BytesIO(data[1:])
    attacker_controller, attacker_location, attacker_sequence, attacker_position = client.read_location(data)
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    attack(client, attacker_controller, attacker_location, attacker_sequence, attacker_position, target_controller, target_location, target_sequence, target_position)

def attack(client, attacker_controller, attacker_location, attacker_sequence, attacker_position, target_controller, target_location, target_sequence, target_position):
    attacking_card = client.get_card(attacker_controller, attacker_location, attacker_sequence)
    if not attacking_card:
        return
    utils.get_ui_stack().play_duel_sound_effect("attack")
    # Each case is one whole sentence rather than a subject glued onto a
    # predicate. "You" and "Your opponent" are not interchangeable pieces once
    # a language inflects the verb after them, and the old version left them
    # in English besides.
    mine = attacker_controller == client.what_player_am_i
    attacking_card_name = attacking_card.get_name() if isinstance(attacking_card, Card) else _("Face down card")
    if target_controller == 0 and target_location == 0 and target_sequence == 0 and target_position == 0:
        # direct attack
        if mine:
            message = _("You prepare to attack directly with {card}.").format(card=attacking_card_name)
        else:
            message = _("Your opponent prepares to attack directly with {card}.").format(card=attacking_card_name)
        utils.output(message, priority=speech.Priority.CRITICAL)
        return
    target_card = client.get_card(target_controller, target_location, target_sequence)
    if not target_card:
        return
    target_card_name = target_card.get_name() if isinstance(target_card, Card) else _("Face down card")
    if mine:
        message = _("You prepare to attack {target} with {card}.")
    else:
        message = _("Your opponent prepares to attack {target} with {card}.")
    utils.output(
        message.format(target=target_card_name, card=attacking_card_name),
        priority=speech.Priority.CRITICAL,
    )
