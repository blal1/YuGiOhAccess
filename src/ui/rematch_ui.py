import struct

from ui.base_ui import HorizontalMenu, StatusMessageWithoutTimelimit
from core import utils
from core.i18n import _

from game.edo import structs

@utils.packet_handler(structs.ServerIdType.REMATCH_WAIT)
def handle_rematch_wait(client, packet_data, packet_length):
    pass

@utils.packet_handler(structs.ServerIdType.REMATCH)
def handle_rematch(client, packet_data, packet_length):
    return show_rematch_ui(client)

@utils.ui_function
def show_rematch_ui(client):
    rematch_menu = HorizontalMenu(_("Do you want to rematch?"))
    rematch_menu.append_item(_("Yes"), lambda: _rematch_yes(client))
    rematch_menu.append_item(_("No"), lambda: _rematch_no(client))
    return rematch_menu

@utils.ui_function
def _rematch_yes(client):
    client.send(structs.ClientIdType.REMATCH, struct.pack("B", 1))
    sm = StatusMessageWithoutTimelimit(_("Waiting for opponent"))
    return sm

@utils.ui_function
def _rematch_no(client):
    client.send(structs.ClientIdType.REMATCH, struct.pack("B", 0))
    sm = StatusMessageWithoutTimelimit(_("Waiting for opponent"))
    return sm
