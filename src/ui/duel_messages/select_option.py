import logging
import io
import struct

from game.card.card import Card
from game.edo import structs

from ui.base_ui import VerticalMenu

from core import utils
from core.i18n import _
from core import variables

logger = logging.getLogger(__name__)

@utils.duel_message_handler(14)
def msg_select_option(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    size = client.read_u8(data)
    options = []
    for i in range(size):
        options.append(client.read_u64(data))
    select_option(client, player, options)
    return data.read()

def select_option(client, player, options):
    logger.debug("Selecting option")
    logger.debug(f"Player id: {player}")
    logger.debug(f"Options: {options}")
    card = None
    opts = []
    for opt in options:
        code = opt >> 20
        stringid = opt & 0xfffff
        string = _option_text(code, stringid)
        opts.append(string)
        if code != 0:
            card = Card(code)
    menu = VerticalMenu(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Select option:")))
    if not card:
        menu.append_item(_("Select option"))
    else:
        menu.append_item(_("Select option for {name}").format(name=card.get_name()))
    for idx, opt in enumerate(opts):
        menu.append_item(_("{option}").format(option=opt), function=lambda idx=idx: select(client, options, idx))
    utils.get_ui_stack().push_ui(menu)

def select(client, options, idx):
    logger.debug(f"Selecting option {idx}")
    logger.debug(f"Options: {options}")
    opt = options[idx]
    code = opt >> 20
    stringid = opt & 0xfffff
    utils.get_ui_stack().pop_ui()
    string = _option_text(code, stringid)
    utils.output(_("Selected option {option}").format(option=string))
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', idx))


def _option_text(code, stringid):
    if code == 0:
        return variables.LANGUAGE_HANDLER.strings['system'].get(stringid, variables.LANGUAGE_HANDLER._("Unknown option %d" % stringid))
    card = Card(code)
    description = card.get_effect_description((code << 4) + stringid, True)
    if description:
        return description
    try:
        return card.strings[stringid]
    except IndexError:
        return variables.LANGUAGE_HANDLER._("Unknown option %d" % stringid)
