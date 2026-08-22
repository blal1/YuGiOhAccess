import io

from game.card.card import Card
from game.card.location_conversion import LocationConversion

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(54)
def msg_set(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    controller, location, sequence, position = client.read_location(data)
    card = Card(code)
    card.set_location_and_position_info(controller, location, sequence, position)
    set(client, card)

def set(client, card):
    controller = card.controller
    location_information = LocationConversion.from_card_location(client, card)
    if controller == client.what_player_am_i:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("You set %s (%s) in %s position.") % (location_information.to_human_readable(), card.get_name(), card.get_position())))
    else:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Your opponent sets %s (%s) in %s position.") % (location_information.to_human_readable(), card.get_name(), card.get_position())))
