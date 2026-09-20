import struct

from game.edo import structs, structs_utils
from ui.base_ui import InputUI, VerticalMenu
from core import utils
from core.i18n import _

from game.card import card_constants

def show_duel_menu(client):
    phase_str = _(card_constants.PHASES.get(client.current_phase, str(client.current_phase)))
    backspace_menu = VerticalMenu(_("Duel Menu"))
    if client.is_it_my_turn:
        backspace_menu.append_item(_("{phase}, your turn. {lp} / {opp_lp} lifepoints. {time} seconds remaining. Turn {turn}").format(
            phase=phase_str, lp=client.player.lifepoints, opp_lp=client.player.opponent_lifepoints,
            time=client.player.turn_timer.get_remaining_time(), turn=client.turn_count))
        if client.player.can_go_to_battle_phase:
            backspace_menu.append_item(_("Battle phase"), function=lambda: send_battle_phase(client))
        if client.player.can_go_to_main_phase2:
            backspace_menu.append_item(_("Main phase 2"), function=lambda: send_main_phase2(client))
        if client.player.can_go_to_end_phase:
            backspace_menu.append_item(_("End turn"), function=lambda: send_end_phase(client))
    else:
        backspace_menu.append_item(_("{phase}, Opponents turn. {lp} / {opp_lp} lifepoints. Turn {turn}").format(
            phase=phase_str, lp=client.player.lifepoints, opp_lp=client.player.opponent_lifepoints, turn=client.turn_count))
    backspace_menu.append_item(_("Read chain"), lambda: read_chain_stack(client))
    backspace_menu.append_item(_("Chat"), lambda: open_chat_input(client))
    backspace_menu.append_item(_("Chat history"), lambda: show_chat_history(client))
    backspace_menu.append_item(_("Surrender"), lambda: confirm_surrender(client))
    backspace_menu.append_item(_("Close"), lambda: utils.get_ui_stack().pop_ui())
    utils.get_ui_stack().push_ui(backspace_menu)


def confirm_surrender(client):
    utils.get_ui_stack().pop_ui()
    menu = VerticalMenu(_("Surrender"))
    menu.append_item(_("Are you sure you want to surrender?"))
    menu.append_item(_("Yes"), lambda: do_surrender(client))
    menu.append_item(_("No"), lambda: utils.get_ui_stack().pop_ui())
    utils.get_ui_stack().push_ui(menu)


def do_surrender(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.SURRENDER)
    utils.output(_("You surrendered."))


def open_chat_input(client):
    utils.get_ui_stack().pop_ui()
    message = InputUI(_("Chat message")).show()
    if not message:
        return
    chat = structs.Chat()
    chat.msg = structs_utils.string_to_u16(message, structs_utils.CHAT_MSG_MAX_LENGTH)
    client.send(structs.ClientIdType.CHAT, chat)
    utils.output(_("Chat message sent."))


def show_chat_history(client):
    utils.get_ui_stack().pop_ui()
    history = getattr(client.memory, "chat_history", [])
    if not history:
        utils.output(_("No chat messages yet."))
        return
    utils.output(_("Chat history:"))
    for player_name, message in history[-30:]:
        utils.output(_("{player}: {message}").format(player=player_name, message=message))


def read_chain_stack(client):
    duel_field = client.get_duel_field()
    utils.output(str(duel_field.get_chain_stack_text()))

def send_battle_phase(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 6))

def send_main_phase2(client):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 2))

def send_end_phase(client):
    utils.get_ui_stack().pop_ui()
    if client.current_phase == 4 or client.current_phase == 0x100: # main phase 1 or main phase 2
        client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 7))
    if client.current_phase == 8 or client.current_phase == 0x80: # battle phase
        client.send(structs.ClientIdType.RESPONSE, struct.pack('I', 3))
