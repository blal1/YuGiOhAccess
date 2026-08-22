import ctypes
import logging

import wx
from core.i18n import _

from ui import duel_state_change_ui # noqa
from ui import rock_paper_scissors_ui # noqa
from ui import room_ui # noqa
from ui import server_ui # noqa
from ui import main_ui # noqa
from ui import rematch_ui # noqa

from ui import duel_messages # noqa

# global handlers that don't fit in any other file
from core import utils

from game.edo import structs, structs_utils

logger = logging.getLogger(__name__)


@utils.packet_handler(structs.ServerIdType.CHAT_2)
def handle_chat_2(client, packet_data, packet_length):
    try:
        player_name, chat_message = _parse_chat_2_packet(packet_data)
    except ValueError:
        logger.warning("Ignoring malformed CHAT_2 packet with length %s", packet_length)
        return
    if client is not None:
        history = getattr(client.memory, "chat_history", [])
        history.append((player_name, chat_message))
        client.memory.chat_history = history[-100:]
    utils.output(_("{player}: {message}").format(player=player_name, message=chat_message))


def _decode_fixed_utf16(data: bytes) -> str:
    return data.decode("utf-16-le", errors="replace").rstrip("\x00")


def _parse_chat_2_packet(packet_data: bytes) -> tuple[str, str]:
    full_packet_size = 2 + 40 + 512
    compact_packet_size = 2 + 512
    if len(packet_data) >= full_packet_size:
        return _decode_fixed_utf16(packet_data[2:42]), _decode_fixed_utf16(packet_data[42:554])
    if len(packet_data) >= compact_packet_size:
        sender = packet_data[0]
        if sender <= 3:
            player_name = _("Player {number}").format(number=sender + 1)
        elif sender == 8:
            player_name = _("Observer")
        else:
            player_name = _("System")
        return player_name, _decode_fixed_utf16(packet_data[2:514])
    raise ValueError(f"CHAT_2 packet too short: {len(packet_data)} bytes")

@utils.packet_handler(structs.ServerIdType.ERROR_MSG)
def handle_error_msg(client, packet_data, packet_length):
    if packet_length == ctypes.sizeof(structs.ErrorMSG):
        m = structs.ErrorMSG.from_buffer_copy(packet_data)
        return handle_error(client, m)
    elif packet_length == ctypes.sizeof(structs.DeckErrrorMSG):
        m = structs.DeckErrrorMSG.from_buffer_copy(packet_data)
        return handle_deck_error(client, m)

def handle_error(client, message):
    if message.msg == 5:
        utils.output(_("Invalid version. Please update the game, or contact support if the issue persists."))
    
def handle_deck_error(client, message):
    logger.error(str(message))
    utils.output(_("{message}").format(message=str(message)))

@utils.packet_handler(structs.ServerIdType.CHANGE_SIDE)
def handle_change_side(client, packet_data, packet_length):
    from ui.side_deck_ui import show_side_deck_ui
    show_side_deck_ui(client)


@utils.packet_handler(structs.ServerIdType.WAITING_SIDE)
def handle_waiting_side(client, packet_data, packet_length):
    utils.output(_("Waiting for opponent to finish side decking."))


@utils.packet_handler(structs.ServerIdType.LEAVE_GAME)
def handle_leave_game(client, packet_data, packet_length):
    utils.output(_("A player left the game."))


@utils.packet_handler(structs.ServerIdType.GAME_MSG)
def handle_game_msg(client, packet_data, packet_length):
    duel_message_id = int(packet_data[0])
    if duel_message_id not in utils.duel_message_handlers:
        logger.error(f"Unhandled duel message id: {duel_message_id}.\nPacket data:\n{packet_data}")
        return
    duel_message_handler = utils.duel_message_handlers[duel_message_id]
    logger.debug(f"Handling duel message id: {duel_message_id}, with handler: {duel_message_handler}")
    wx.CallAfter(duel_message_handler, client, packet_data, packet_length)
    
