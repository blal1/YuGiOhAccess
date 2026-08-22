import io
import struct

from game.edo import structs
from core import utils
from core.i18n import _

from ui.base_ui import VerticalMenu

@utils.duel_message_handler(143)
def msg_announce_number(client, data, length):
    data = io.BytesIO(data[1:])
    # print out the rest of the data
    player = client.read_u8(data)
    size = client.read_u8(data)
    options = []
    for i in range(size):
        options.append(client.read_u64(data))
    announce_number(client, player, options)

def announce_number(client, player, options):
    menu = VerticalMenu(_("Select a number"))
    for i, option in enumerate(options):
        menu.append_item(_("{option}").format(option=str(option)), function=lambda i=i, options=options: _send_response(client, options, i))
    utils.get_ui_stack().push_ui(menu)

def _send_response(client, options, selected_index):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('i', selected_index))
