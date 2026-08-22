import io
import logging

from core import utils
from core.i18n import _
from core import variables

from game.card.location_conversion import LocationConversion
from game.edo import structs

logger = logging.getLogger(__name__)

selected_zones = []

@utils.duel_message_handler(18)
@utils.duel_message_handler(24)
def msg_select_place(client, data, data_len):
    global selected_zones
    selected_zones = []
    data = io.BytesIO(data)
    _ = client.read_u8(data)
    player = client.read_u8(data)
    count = client.read_u8(data)
    if count == 0:
        count = 1
    flag = client.read_u32(data)
    select_place(client, player, count, flag)

def select_place(client, player, count, flag):
    specs = client.flag_to_usable_cardspecs(flag)
    logger.debug(f"Specs: {specs}")
    client.get_duel_field().tab_order.set_tabable_items(specs)
    locations = []
    for spec in specs:
        converted_location_from_spec = LocationConversion.from_zone_key(client, spec)
        logger.debug(f"Converted location: {converted_location_from_spec}")
        locations.append(converted_location_from_spec)
    if count == 1:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Select place for card, one of %s.") % ", ".join([loc.to_human_readable() for loc in locations])))
    else:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Select %d places for card, from %s.") % (count, ", ".join([loc.to_human_readable() for loc in locations]))))
    old_handle_enter = client.get_duel_field().handle_enter
    client.get_duel_field().handle_enter = lambda: process_selected_zone(client, player, count, locations, old_handle_enter)

def process_selected_zone(client, player, count, locations, old_handler):
    global selected_zones
    selected_zone = client.get_duel_field().get_zone_from_current_position()
    if not selected_zone:
        logger.debug("No zone selected. This might be the extra deck")
        utils.output(_("Invalid zone selected."))
        return
    logger.debug(f"Locations: {locations}, selected: {selected_zone.label}")
    if LocationConversion.from_zone_key(client, selected_zone.label) not in locations:
        utils.output(_("Invalid zone selected."))
        return
    selected_zones.append(selected_zone)
    if len(selected_zones) == count:
        resolve_select_place(client, player, selected_zones, old_handler)
        
def resolve_select_place(client, player, selected_zones, old_handle_enter):
    resp = b""
    for zone in selected_zones:
        location, sequence, opponent = client.useful_spec_to_location(zone.label)
        logger.debug(f"Resolving place: location={location}, sequence={sequence}, opponent={opponent}")
        if opponent:
            plr = 1 - player
        else:
            plr = player
        resp += bytes([plr, location, sequence])
    client.send(structs.ClientIdType.RESPONSE, resp)
    client.get_duel_field().handle_enter = old_handle_enter
