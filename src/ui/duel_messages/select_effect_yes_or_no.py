import io
import struct

from game.card.card import Card
from game.edo import structs

from core import utils
from core.i18n import _

from ui.base_ui import VerticalMenu
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_SELECT_EFFECTYN)
def msg_select_effectyn(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    card = Card(client.read_u32(data))
    controller, location, seq, pos = client.read_location(data)
    card.set_location_and_position_info(controller, location, seq, pos)
    desc = client.read_u64(data)
    select_effectyn(client, player, card, desc)

def select_effectyn(client, player, card, desc):
    yes_or_no_menu = VerticalMenu(_("Activate effect"))
    question = _("Do you want to use {name}'s effect?").format(name=card.get_name())
    s = card.get_effect_description(desc, True)
    if s:
        question += f"\n{s}"
    yes_or_no_menu.append_item(str(question), function=lambda: utils.output(str(card)))
    yes_or_no_menu.append_item(_("Yes"), function=lambda: yes(client))
    yes_or_no_menu.append_item(_("No"), function=lambda: no(client))
    utils.get_ui_stack().push_ui(yes_or_no_menu)



def yes(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 1))    

def no(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 0))    
