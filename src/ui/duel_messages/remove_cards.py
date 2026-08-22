import io

from game.card.location_conversion import LocationConversion

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(190)
def msg_remove_cards(client, data, data_length):
    data = io.BytesIO(data[1:])
    count = client.read_u32(data)
    locations = []
    for i in range(count):
        controller, location, sequence, position = client.read_location(data)
        locations.append((controller, location, sequence, position))
    remove_cards(client, locations)

def remove_cards(client, locations):
    for loc in locations:
        controller, location, sequence, position = loc
        location_converted = LocationConversion(client, controller, location, sequence)
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s removed.") % location_converted.to_human_readable()))
