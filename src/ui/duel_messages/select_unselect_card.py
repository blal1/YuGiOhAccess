import io
import logging
import struct

from game.card.card import Card
from game.edo import structs
from game.card.location_conversion import LocationConversion

from ui.base_ui import VerticalMenu

from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_SELECT_UNSELECT_CARD)
def msg_select_unselect_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    finishable = client.read_u8(data)
    cancelable = client.read_u8(data)
    min = client.read_u32(data)
    max = client.read_u32(data)
    select_size = client.read_u32(data)
    select_cards = []
    for i in range(select_size):
        code = client.read_u32(data)
        controller, location, sequence, position = client.read_location(data)
        card = Card(code)
        card.set_location_and_position_info(controller, location, sequence, position)
        select_cards.append(card)
    unselect_size = client.read_u32(data)
    unselect_cards = []
    for i in range(unselect_size):
        code = client.read_u32(data)
        controller, location, sequence, position = client.read_location(data)
        card = Card(code)
        card.set_location_and_position_info(controller, location, sequence, position)
        unselect_cards.append(card)
    select_unselect_card(client, player, finishable, cancelable, min, max, select_cards, unselect_cards)
    end = data.read()
    if len(end) > 0:
        logger.warning(f"msg_select_unselect_card had {len(end)} bytes left over")

def select_unselect_card(client, player, finishable, cancelable, min, max, select_cards, unselect_cards):
    card_list = select_cards + unselect_cards
    logger.debug(f"Selecting cards from {card_list}")
    selection_menu = VerticalMenu(_("Select cards ({min}-{max}):").format(min=min, max=max))
    for i, card in enumerate(card_list):
        location_info = LocationConversion.from_card_location(client, card)
        state = ""
        if card in select_cards:
            state = _("Unselected")
        else:
            state = _("Selected")
        selection_menu.append_item(
            _("{index}: {name} in {location} ({state})").format(
                index=i + 1,
                name=card.get_name(),
                location=location_info.to_human_readable(),
                state=state,
            ),
            function=lambda i=i: select_unselect_specific_card(client, i),
        )
    if cancelable and not finishable:
        selection_menu.append_cancel_item(_("Cancel"), function=lambda: select_unselect_specific_card(client, -1))
    if finishable:
        selection_menu.append_item(_("Finish"), function=lambda: select_unselect_specific_card(client, -1))
    utils.get_ui_stack().push_ui(selection_menu)

def select_unselect_specific_card(client, index):
    logger.debug(f"Selecting card {index}")
    if index == -1:
        logger.debug("Cancel")
        utils.get_ui_stack().pop_ui()
        client.send(structs.ClientIdType.RESPONSE, struct.pack('i', -1))
        return
    buf = b""
    buf += struct.pack('I', 1)
    buf += struct.pack('I', index)
    logger.debug(f"Selected index {index}")
    logger.debug(f"Message: {buf}")
    utils.get_ui_stack().pop_ui()
    logger.debug(buf)
    client.send(structs.ClientIdType.RESPONSE, buf)
