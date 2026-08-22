import logging
import io
import struct

from game.card.card import Card
from game.edo import structs

from core import utils
from core.i18n import _
from core import variables
from ui.base_ui import VerticalMenu


logger = logging.getLogger(__name__)


@utils.duel_message_handler(13)
def msg_select_yesno(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    description = client.read_u64(data)
    select_yes_no(client, player, description)
    

def select_yes_no(client, player, desc):
    code = desc >> 20
    stringid = desc & 0xfffff
    card = None
    logger.debug("Selecting yes or no")
    logger.debug(f"Player id: {player}")
    logger.debug(f"Code: {code}")
    logger.debug(f"String id: {stringid}")
    if code == 0:
        question = variables.LANGUAGE_HANDLER.strings['system'].get(stringid, variables.LANGUAGE_HANDLER._("Unknown option %d" % stringid))
    else:
        card = Card(code)
        question = variables.LANGUAGE_HANDLER._("Do you want to use %s's effect?")%(card.get_name())
        effect_description = card.get_effect_description((code << 4) + stringid, True)
        if effect_description:
            question += "\n" + effect_description
    yes_or_no_menu = VerticalMenu(_("Select yes or no"))
    yes_or_no_menu.append_item(
        _("{question}").format(question=question),
        function=lambda: utils.output(_("{card}").format(card=str(card)) if card else _("{question}").format(question=question)),
    )
    yes_or_no_menu.append_item(_("Yes"), function=lambda: yes(client))
    yes_or_no_menu.append_item(_("No"), function=lambda: no(client))
    utils.get_ui_stack().push_ui(yes_or_no_menu)



def yes(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 1))    

def no(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 0))    
