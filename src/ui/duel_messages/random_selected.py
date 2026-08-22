import io

from game.card.location_conversion import LocationConversion
from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(81)
def msg_random_selected(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    locations = []
    for i in range(count):
        controller, location, sequence, position = client.read_location(data)
        locations.append(LocationConversion(client, controller, location, sequence))
    random_selected(client, player, locations)

def random_selected(client, player, locations):
    if player == client.what_player_am_i:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("You randomly selected the following locations:")))
    else:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Your opponent randomly selected the following locations:")))
    for loc in locations:
        utils.output(_("{location}").format(location=loc.to_human_readable()))
