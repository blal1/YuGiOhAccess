import io

from game.card.location_conversion import LocationConversion
from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_CARD_SELECTED)
def msg_card_selected(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u32(data)
    locations = []
    for i in range(count):
        controller, location, sequence, position = client.read_location(data)
        locations.append(LocationConversion(client, controller, location, sequence))
    card_selected(client, locations)

def card_selected(client, locations):
    utils.output(_("The following locations were selected:"))
    for loc in locations:
        utils.output(loc.to_human_readable())
