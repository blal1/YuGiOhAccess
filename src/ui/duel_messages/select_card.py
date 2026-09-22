import io
import logging
import struct

import wx

from game.card.card import Card
from game.card import card_constants
from game.card.location_conversion import LocationConversion
from game.edo import structs

from ui.base_ui import VerticalMenu
from ui.selection_limit import SelectionLimiter

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_SELECT_TRIBUTE)
def msg_select_tribute(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    cancelable = client.read_u8(data)
    min = client.read_u32(data)
    max = client.read_u32(data)
    size = client.read_u32(data)
    cards = []
    for i in range(size):
        code = client.read_u32(data)
        card = Card(code)
        # in this case, we can't use the client.read_location, because it doesn't send the position regardless of what it is
        card.controller = client.read_u8(data)
        card.location = client.read_u8(data)
        card.sequence = client.read_u32(data)
        card.release_param = client.read_u8(data)
        cards.append(card)
    select_tribute(client, player, cancelable, min, max, cards)

@utils.duel_message_handler(message_constants.MSG_SELECT_CARD)
def msg_select_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    cancelable = client.read_u8(data)
    min = client.read_u32(data)
    max = client.read_u32(data)
    size = client.read_u32(data)
    cards = []
    logger.debug(f"Size: {size}")
    for i in range(size):
        code = client.read_u32(data)
        logger.debug(f"Code: {code}")
        controller, location, sequence, position = client.read_location(data)
        if code != 0:
            card = Card(code)
            card.set_location_and_position_info(controller, location, sequence, position)
            cards.append(card)
        else:
            card = Card(0)
            card.controller = controller
            card.location = location
            card.sequence = sequence
            card.position = card_constants.POSITION(position)
            cards.append(card)
    select_card(client, player, cancelable, min, max, cards)

def select_card(client, player, cancelable, min_cards, max_cards, cards, is_tribute=False):
    presentable_cards = []
    for selectable_card in cards:
        location_information = LocationConversion.from_card_location(client, selectable_card)
        if selectable_card.code != 0:
            presentable_cards.append(_("{name} in {location}").format(name=selectable_card.get_name(), location=location_information.to_human_readable()))
        else:
            presentable_cards.append(_("Face down card in {location}").format(location=location_information.to_human_readable()))
    show_menu_with_presentable_cards(client, cards, presentable_cards, min_cards, max_cards, is_tribute, cancelable=cancelable)



def select_tribute(client, *args, **kwargs):
    kwargs['is_tribute'] = True
    select_card(client, *args, **kwargs)

def show_menu_with_presentable_cards(client, cards, presentable_cards, min_cards, max_cards, is_tribute, cancelable=False):
    question = _("Select {min} to {max} card(s) as tribute").format(min=min_cards, max=max_cards) if is_tribute else _("Select {min} to {max} card(s)").format(min=min_cards, max=max_cards)
    select_card_menu = VerticalMenu(str(question))
    select_card_menu.append_item(str(question))
    # The duel accepts at most max_cards, so the menu holds the player to it
    # rather than letting them build an answer that will be thrown back.
    limiter = SelectionLimiter(max_cards)
    for card in presentable_cards:
        checkbox = select_card_menu.append_item(wx.CheckBox, label=card)
        limiter.add(checkbox, label=card)
    if cancelable:
        select_card_menu.append_cancel_item(_("Cancel"), function=lambda: cancel_card_selection(client))
        utils.output(_("Press Escape to cancel selection"))
    select_card_menu.append_item(_("Finish"), function=lambda: finish_card_selection(client, select_card_menu, cards, min_cards, max_cards, is_tribute))
    utils.get_ui_stack().push_ui(select_card_menu)

def finish_card_selection(client, select_card_menu, cards, min_cards, max_cards, is_tribute):
    card_checkboxes = []
    for row in select_card_menu.cells:
        if isinstance(row[0], wx.CheckBox):
            card_checkboxes.append(row[0])
    selected_cards = []
    for i, checkbox in enumerate(card_checkboxes):
        if checkbox.IsChecked():
            selected_cards.append(i)
    logger.debug(f"Selected cards:\nLength: {len(selected_cards)}\n{selected_cards}")
    # Last line of defence. The menu already stops the player ticking too many,
    # but an answer outside the range is one the core throws straight back, and
    # a refusal here is far easier to act on than a retry prompt.
    if len(selected_cards) < min_cards:
        utils.output(
            _("Select at least {min} card(s). You have selected {count}.").format(
                min=min_cards, count=len(selected_cards)
            ),
            priority=speech.Priority.CRITICAL,
        )
        return
    if max_cards and len(selected_cards) > max_cards:
        utils.output(
            _("Select at most {max} card(s). You have selected {count}.").format(
                max=max_cards, count=len(selected_cards)
            ),
            priority=speech.Priority.CRITICAL,
        )
        return
    buf = b""
    # pack an uint with the value of 1, to signal to the server
    buf += struct.pack('I', 1)
    # first pack the size of the selected cards into an uint32
    buf += struct.pack('I', len(selected_cards))
    for selected_card_index in selected_cards:
        # add the index to the buffer, as an uint16
        buf += struct.pack('H', selected_card_index)
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, buf)


def cancel_card_selection(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 0xFFFFFFFF))
