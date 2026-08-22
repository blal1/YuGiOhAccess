import io
import logging
import struct

import wx

from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import structs
from ui.base_ui import VerticalMenu

logger = logging.getLogger(__name__)


@utils.duel_message_handler(17)
def msg_select_counter(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    counter_type = client.read_u16(data)
    quantity = client.read_u16(data)
    size = client.read_u32(data)
    cards = []
    for _ in range(size):
        code = client.read_u32(data)
        controller = client.read_u8(data)
        location = client.read_u8(data)
        sequence = client.read_u8(data)
        card_counter_count = client.read_u16(data)
        card = Card(code)
        card.counter_count = card_counter_count
        cards.append(card)
    select_counter(client, player, counter_type, quantity, cards)


def select_counter(client, player, counter_type, quantity, cards):
    menu = VerticalMenu(_("Select counters"))
    menu.append_item(_("Remove {quantity} counter(s)").format(quantity=quantity))
    for i, card in enumerate(cards):
        slider = menu.append_item(wx.Slider, label=_("{name} ({count} counters)").format(name=card.get_name(), count=card.counter_count))
        slider.SetRange(0, min(card.counter_count, quantity))
        slider.SetValue(0)
    menu.append_item(_("Finish"), function=lambda: finish_counter_selection(client, menu, cards, quantity))
    utils.get_ui_stack().push_ui(menu)


def finish_counter_selection(client, menu, cards, quantity):
    counters = []
    for row in menu.cells:
        if isinstance(row[0], wx.Slider):
            counters.append(row[0].GetValue())
    if sum(counters) != quantity:
        utils.output(_("You must select exactly {quantity} counter(s). Currently selected: {current}").format(quantity=quantity, current=sum(counters)))
        return
    buf = struct.pack('I', 1)
    for c in counters:
        buf += struct.pack('H', c)
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, buf)
