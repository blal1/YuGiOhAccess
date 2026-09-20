import io
import logging
import struct

import wx

from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import structs
from ui.base_ui import VerticalMenu
from game.edo import message_constants

logger = logging.getLogger(__name__)


@utils.duel_message_handler(message_constants.MSG_SORT_CARD)
def msg_sort_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    size = client.read_u32(data)
    cards = []
    for _unused in range(size):
        code = client.read_u32(data)
        controller = client.read_u8(data)
        location = client.read_u8(data)
        sequence = client.read_u32(data)
        card = Card(code)
        cards.append(card)
    sort_card(client, player, cards)


def sort_card(client, player, cards):
    order = list(range(len(cards)))
    sort_card_step(client, cards, order, [])


def sort_card_step(client, remaining_cards, remaining_indices, selected_order):
    if len(remaining_cards) == 1:
        selected_order.append(remaining_indices[0])
        finish_sort(client, selected_order)
        return
    menu = VerticalMenu(_("Sort cards"))
    menu.append_item(_("Select the next card in order ({done}/{total})").format(done=len(selected_order) + 1, total=len(selected_order) + len(remaining_cards)))
    for i, card in enumerate(remaining_cards):
        menu.append_item(card.get_name(), function=lambda idx=i: pick_card(client, remaining_cards, remaining_indices, selected_order, idx))
    utils.get_ui_stack().push_ui(menu)


def pick_card(client, remaining_cards, remaining_indices, selected_order, pick_idx):
    utils.get_ui_stack().pop_ui()
    selected_order.append(remaining_indices[pick_idx])
    new_cards = remaining_cards[:pick_idx] + remaining_cards[pick_idx + 1:]
    new_indices = remaining_indices[:pick_idx] + remaining_indices[pick_idx + 1:]
    sort_card_step(client, new_cards, new_indices, selected_order)


def finish_sort(client, order):
    buf = struct.pack('I', 1)
    for idx in order:
        buf += struct.pack('B', idx)
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, buf)
