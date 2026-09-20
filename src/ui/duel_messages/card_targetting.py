import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_CARD_TARGET)
def msg_card_target(client, data, data_length, cancelled=False):
    data = io.BytesIO(data[1:])
    controller, location, sequence, position = client.read_location(data)
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    card = client.get_card(controller, location, sequence)
    target = client.get_card(target_controller, target_location, target_sequence)
    if not card or not target:
        logger.error(f"Card or target not found\nCard info: {controller}, {location}, {sequence}\nTarget info: {target_controller}, {target_location}, {target_sequence},\Found card from duel field: {card}\nFound target from duel field: {target}")
    card_target(client, card, target, cancelled)

@utils.duel_message_handler(message_constants.MSG_CANCEL_TARGET)
def msg_cancel_card_target(client, data, data_length):
    return msg_card_target(client, data, data_length, True)

def card_target(client, card, target, cancelled):
    if not cancelled:
        utils.output(_("{card} targets {target}.").format(card=card.get_name(), target=target.get_name()), priority=speech.Priority.CRITICAL)
        utils.get_ui_stack().play_duel_sound_effect("aim")
    else:
        utils.output(_("{card} cancels targeting {target}.").format(card=card.get_name(), target=target.get_name()), priority=speech.Priority.INFO)


