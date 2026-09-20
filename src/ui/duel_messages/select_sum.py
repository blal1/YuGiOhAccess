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


@utils.duel_message_handler(message_constants.MSG_SELECT_SUM)
def msg_select_sum(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    select_mode = client.read_u8(data)
    target_sum = client.read_u32(data)
    min_cards = client.read_u32(data)
    max_cards = client.read_u32(data)
    must_select_count = client.read_u32(data)
    must_select = []
    for _unused in range(must_select_count):
        code = client.read_u32(data)
        controller = client.read_u8(data)
        location = client.read_u8(data)
        sequence = client.read_u32(data)
        param = client.read_u32(data)
        card = Card(code)
        card.param = param
        must_select.append(card)
    can_select_count = client.read_u32(data)
    can_select = []
    for _unused in range(can_select_count):
        code = client.read_u32(data)
        controller = client.read_u8(data)
        location = client.read_u8(data)
        sequence = client.read_u32(data)
        param = client.read_u32(data)
        card = Card(code)
        card.param = param
        can_select.append(card)
    select_sum(client, player, select_mode, target_sum, min_cards, max_cards, must_select, can_select)


def select_sum(client, player, select_mode, target_sum, min_cards, max_cards, must_select, can_select):
    menu = VerticalMenu(_("Select cards"))
    if select_mode == 0:
        menu.append_item(_("Select cards with levels/ranks that total exactly {target}").format(target=target_sum))
    else:
        menu.append_item(_("Select cards with levels/ranks that total at least {target}").format(target=target_sum))
    if must_select:
        for card in must_select:
            level = card.param & 0xffff
            menu.append_item(_("{name} (Level {level}) - must select").format(name=card.get_name(), level=level))
    for card in can_select:
        level = card.param & 0xffff
        menu.append_item(wx.CheckBox, label=_("{name} (Level {level})").format(name=card.get_name(), level=level))
    menu.append_item(_("Finish"), function=lambda: finish_sum_selection(client, menu, must_select, can_select, target_sum, select_mode))
    utils.get_ui_stack().push_ui(menu)


def finish_sum_selection(client, menu, must_select, can_select, target_sum, select_mode):
    selected_indices = []
    checkboxes = []
    for row in menu.cells:
        if isinstance(row[0], wx.CheckBox):
            checkboxes.append(row[0])
    for i, checkbox in enumerate(checkboxes):
        if checkbox.IsChecked():
            selected_indices.append(i)
    total = sum((card.param & 0xffff) for card in must_select)
    for idx in selected_indices:
        total += can_select[idx].param & 0xffff
    if select_mode == 0 and total != target_sum:
        utils.output(_("Total must be exactly {target}. Current: {current}").format(target=target_sum, current=total))
        return
    if select_mode == 1 and total < target_sum:
        utils.output(_("Total must be at least {target}. Current: {current}").format(target=target_sum, current=total))
        return
    buf = struct.pack('I', 1)
    total_selected = len(must_select) + len(selected_indices)
    buf += struct.pack('I', total_selected)
    for i in range(len(must_select)):
        buf += struct.pack('H', i)
    for idx in selected_indices:
        buf += struct.pack('H', len(must_select) + idx)
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, buf)
