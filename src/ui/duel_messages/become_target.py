import io
import logging

from game.card import card_constants
from game.card.location_conversion import LocationConversion
from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_BECOME_TARGET)
def msg_become_target(client, data, data_length):
    data = io.BytesIO(data[1:])
    client.read_u32(data)  # chain index, unused
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    become_target(client, target_controller, target_location, target_sequence, target_position)


def become_target(client, target_controller, target_location, target_sequence, target_position):
    card = client.get_card(target_controller, target_location, target_sequence)
    if not card:
        zone_key = LocationConversion(client, target_controller, target_location, target_sequence).to_zone_key()
        logger.warning("Ignoring become_target for card missing from zone %s", zone_key)
        return
    card.position = card_constants.POSITION(target_position)
    location_info = LocationConversion.from_card_location(client, card)
    if target_controller == client.what_player_am_i:
        message = _("You target %s")
    else:
        message = _("Your opponent targets %s")
    target_card_name = card.get_name()
    if card.controller != client.what_player_am_i and card.position & card_constants.POSITION.FACE_DOWN:
        target_card_name = _("%s card") % location_info.to_human_readable()
    utils.output(message % target_card_name, priority=speech.Priority.CRITICAL)
    utils.get_ui_stack().play_duel_sound_effect("aim")
