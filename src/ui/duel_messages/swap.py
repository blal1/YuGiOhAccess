import io

from game.card.card import Card
from game.card.location_conversion import LocationConversion

from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_SWAP)
def msg_swap(client, data, data_length):
    data = io.BytesIO(data[1:])
    code1 = client.read_u32(data)
    controller1, location1, sequence1, position1 = client.read_location(data)
    code2 = client.read_u32(data)
    controller2, location2, sequence2, position2 = client.read_location(data)

    card1 = Card(code1)
    card1.set_location_and_position_info(controller1, location1, sequence1, position1)
    card2 = Card(code2)
    card2.set_location_and_position_info(controller2, location2, sequence2, position2)
    swap(client, card1, card2)
    return data.read()

def swap(client, card1, card2):
    location_information = LocationConversion.from_card_location(client, card1)
    swapped_towards = ""
    if card2.controller == client.what_player_am_i:
        swapped_towards = "you"
    else:
        swapped_towards = "your opponent"
        utils.output(_("card {name} swapped controller to {plname} and is now located at {targetspec}.").format(plname=swapped_towards, targetspec=location_information.to_human_readable(), name=card1.get_name()))
