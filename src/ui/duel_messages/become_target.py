import io

from game.card import card_constants
from game.card.location_conversion import LocationConversion
from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(83)
def msg_become_target(client, data, data_length):
    data = io.BytesIO(data[1:])
    _ = client.read_u32(data)
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    become_target(client, target_controller, target_location, target_sequence, target_position)


def become_target(client, target_controller, target_location, target_sequence, target_position):
    card = client.get_card(target_controller, target_location, target_sequence)
    if not card:
        location_info = LocationConversion(client, target_controller, target_location, target_sequence)
        raise ValueError(f"Card not found. Tried to get card in location: {location_info.to_zone_key()}\n{client.get_duel_field().zones.keys()}")
    card.position = card_constants.POSITION(target_position)
    location_info = LocationConversion.from_card_location(client, card)
    _message = ""
    if target_controller == client.what_player_am_i:
        _message = variables.LANGUAGE_HANDLER._("You target %s")
    else:
        _message = variables.LANGUAGE_HANDLER._("Your opponent targets %s")

    if not card:
        return
    target_card_name = card.get_name()
    if card.controller != client.what_player_am_i and card.position & card_constants.POSITION.FACE_DOWN:
        target_card_name = variables.LANGUAGE_HANDLER._("%s card") % location_info.to_human_readable()
    utils.output(_("{message}").format(message=_message % target_card_name))
    utils.get_ui_stack().play_duel_sound_effect("aim")
