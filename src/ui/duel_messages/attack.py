import io

from game.card.card import Card
from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(110)
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
    if target_controller == 0 and target_location == 0 and target_sequence == 0 and target_position == 0:
        # direct attack
        _player = ""
        if attacker_controller == client.what_player_am_i:
            _player = "You prepare"
        else:
            _player = "Your opponent prepares"
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s to attack with %s") % (_player, attacking_card.get_name())))
        return
    target_card = client.get_card(target_controller, target_location, target_sequence)
    if not target_card:
        return
    _player = ""
    if attacker_controller == client.what_player_am_i:
        _player = "You"
    else:
        _player = "Your opponent"
    attacking_card_name = "Face down card"
    if isinstance(attacking_card, Card):
        attacking_card_name = attacking_card.get_name()
    target_card_name = "Face down card"
    if isinstance(target_card, Card):
        target_card_name = target_card.get_name()
    utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s prepares to attack %s with %s") % (_player, target_card_name, attacking_card_name)))
