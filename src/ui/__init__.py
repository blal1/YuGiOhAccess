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
from core import speech
from core import utils

from game.edo import structs
from game.edo import message_routing

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
    """Say why the server refused the deck, rather than reading out a struct.

    This used to speak the repr of a ctypes structure, which told a player
    with a 39 card deck approximately nothing.
    """
    logger.error("Deck refused by the server: %s", message)
    utils.output(_deck_error_text(message), priority=speech.Priority.CRITICAL)


def _card_name(code):
    if not code:
        return ""
    try:
        from game.card.card import Card

        return Card(int(code)).get_name()
    except Exception:
        logger.debug("Deck error named a card we could not load: %s", code, exc_info=True)
        return str(code)


def _deck_error_text(message):
    # The reasons as EDOPro numbers them; see server/deck_check.py.
    error_type = int(getattr(message, "type", 0))
    count = getattr(message, "count", None)
    got = int(getattr(count, "got", 0) or 0)
    minimum = int(getattr(count, "min", 0) or 0)
    maximum = int(getattr(count, "max", 0) or 0)
    name = _card_name(getattr(message, "code", 0))

    if error_type == 6:
        return _("Your main deck has {got} cards. It must have between {min} and {max}.").format(
            got=got, min=minimum, max=maximum)
    if error_type == 7:
        return _("Your extra deck has {got} cards. At most {max} are allowed.").format(
            got=got, max=maximum)
    if error_type == 8:
        return _("Your side deck has {got} cards. At most {max} are allowed.").format(
            got=got, max=maximum)
    if error_type == 4:
        return _("Your deck contains a card this server does not know: {card}.").format(card=name)
    if error_type == 1:
        return _("The banlist allows {max} copies of {card}, and your deck has {got}.").format(
            max=maximum, card=name, got=got)
    if error_type == 5:
        return _("Your deck has {got} copies of {card}. At most {max} are allowed.").format(
            got=got, card=name, max=maximum)
    return _("The server refused your deck.")

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


@utils.packet_handler(structs.ServerIdType.CHAT)
def handle_chat(client, packet_data, packet_length):
    """Chat from a server that predates CHAT_2. Declared nowhere before this."""
    if packet_length < 2:
        logger.warning("Ignoring short CHAT packet (%s bytes)", packet_length)
        return
    sender = int.from_bytes(packet_data[:2], "little")
    message = _decode_fixed_utf16(packet_data[2:])
    player_name = _chat_sender_name(client, sender)
    if client is not None:
        history = getattr(client.memory, "chat_history", [])
        history.append((player_name, message))
        client.memory.chat_history = history[-100:]
    utils.output(_("{player}: {message}").format(player=player_name, message=message))


def _chat_sender_name(client, sender):
    """Turn a seat index into something worth saying out loud."""
    users = getattr(getattr(client, "room", None), "users", None) or []
    if 0 <= sender < len(users):
        name = users[sender].get("name") if isinstance(users[sender], dict) else None
        if name:
            return name
    if sender < 4:
        return _("Player {number}").format(number=sender + 1)
    if sender == 8:
        return _("Observer")
    return _("System")


@utils.packet_handler(structs.ServerIdType.WATCH_CHANGE)
def handle_watch_change(client, packet_data, packet_length):
    """Spectator count changed. Declared in structs.py but never handled before,
    which is why the client had no usable spectator mode."""
    if packet_length < ctypes.sizeof(structs.StocWatchChange):
        logger.warning("Ignoring short WATCH_CHANGE packet (%s bytes)", packet_length)
        return
    message = structs.StocWatchChange.from_buffer_copy(packet_data)
    previous = getattr(client.memory, "watch_count", None)
    client.memory.watch_count = message.watch_count
    if previous == message.watch_count:
        return
    utils.output(
        _("{count} spectator(s) watching.").format(count=message.watch_count),
        priority=speech.Priority.AMBIENT,
    )


@utils.packet_handler(structs.ServerIdType.CATCHUP)
def handle_catchup(client, packet_data, packet_length):
    """The server is fast forwarding us through the duel we missed.

    While catching up the duel messages arrive as a burst. Speaking every one of
    them would take minutes, so they are logged silently and summarised here;
    F9 replays them.
    """
    catching_up = bool(packet_data[0]) if packet_data else False
    client.memory.catching_up = catching_up
    if catching_up:
        # Announce before arming suppression, or this message is suppressed too.
        utils.output(_("Catching up with the duel, please wait."), priority=speech.Priority.CRITICAL)
        speech.CATCH_UP.start()
        return
    skipped = speech.CATCH_UP.finish()
    if skipped:
        utils.output(
            _("Caught up. {count} message(s) were skipped; press F9 to review them.").format(count=skipped),
            priority=speech.Priority.CRITICAL,
        )
    else:
        utils.output(_("Caught up with the duel."), priority=speech.Priority.CRITICAL)


def log_incoming_duel_message(client, packet_data):
    """One line per duel message, so a duel can be replayed from the log.

    The addressed player is the part worth having: a prompt that names anyone
    but us means the server is asking us to act for someone else, which is how
    the bot ended up playing the human's turns.
    """
    duel_message_id = int(packet_data[0])
    name = message_routing.message_name(duel_message_id)
    target = message_routing.addressed_player(duel_message_id, packet_data)
    me = getattr(client, "what_player_am_i", -1)
    if target is None:
        logger.debug("Duel message %s (%d bytes)", name, len(packet_data))
        return
    who = "me" if target == me else f"player {target}"
    if duel_message_id in message_routing.PROMPT_MESSAGES and target != me:
        logger.warning(
            "Prompt %s addressed to player %d, but we are player %d. "
            "Answering it would act for the other duelist.",
            name, target, me,
        )
    else:
        logger.debug("Duel message %s for %s (%d bytes)", name, who, len(packet_data))


def remember_prompt(client, duel_message_id, packet_data, packet_length):
    """Keep the last question the duel asked us, so it can be asked again.

    MSG_RETRY means the core rejected our answer and is still waiting for a
    good one. Without the question in hand there is nothing to put back on
    screen, so the duel simply stopped: the player was told the answer was
    invalid and then had nothing left to answer.
    """
    if client is None or duel_message_id not in message_routing.PROMPT_MESSAGES:
        return
    target = message_routing.addressed_player(duel_message_id, packet_data)
    if target is not None and target != getattr(client, "what_player_am_i", -1):
        return
    client.memory.last_prompt = (duel_message_id, bytes(packet_data), packet_length)


@utils.packet_handler(structs.ServerIdType.GAME_MSG)
def handle_game_msg(client, packet_data, packet_length):
    duel_message_id = int(packet_data[0])
    log_incoming_duel_message(client, packet_data)
    if duel_message_id not in utils.duel_message_handlers:
        logger.error(f"Unhandled duel message id: {duel_message_id}.\nPacket data:\n{packet_data}")
        return
    remember_prompt(client, duel_message_id, packet_data, packet_length)
    duel_message_handler = utils.duel_message_handlers[duel_message_id]
    logger.debug(f"Handling duel message id: {duel_message_id}, with handler: {duel_message_handler}")
    wx.CallAfter(duel_message_handler, client, packet_data, packet_length)
    
