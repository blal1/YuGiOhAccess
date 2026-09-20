import io
import struct

import logging

from game.edo import structs
from core import utils
from core.i18n import _
from core import variables

from ui.base_ui import InputUI, VerticalMenu
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_ANNOUNCE_CARD)
def msg_announce_card(client, data, length):
    data = io.BytesIO(data[1:])
    # print out the rest of the data
    player = client.read_u8(data)
    size = client.read_u8(data)
    options = []
    for i in range(size):
        options.append(client.read_u64(data))
    announce_card(client, player, options)

def announce_card(client, player, options):
    logger.error("announce card options: %s", options)
    menu = InputUI(_("Select a card"))
    card_name_to_search_for = menu.show()
    cards_found = variables.LANGUAGE_HANDLER.get_cards_by_partial_name(card_name_to_search_for)
    if not cards_found:
        utils.output(_("No cards found"))
        return announce_card(client, player, options)
    if len(cards_found.keys()) > 1:
        menu = VerticalMenu(_("Select a card"))
        for name in cards_found:
            menu.append_item(str(name), function=lambda code=cards_found[name]: _send_response(client, code, True))
        utils.get_ui_stack().push_ui(menu)
        return
    code = list(cards_found.values())[0]
    _send_response(client, code, False)

def _send_response(client, code, pop_last_ui):
    if pop_last_ui:
        utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', code))
