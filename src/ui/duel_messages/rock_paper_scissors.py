"""MSG_ROCK_PAPER_SCISSORS and MSG_HAND_RES: the in-duel hand game.

These are the core's own rock/paper/scissors, used by cards that make the
players throw hands mid duel. They are distinct from the lobby STOC_CHOOSE_RPS
handled in ``ui/rock_paper_scissors_ui.py``, which decides who starts the match.

Wire format:

    MSG_ROCK_PAPER_SCISSORS: u8 player being asked
    MSG_HAND_RES:            u8 packed, where bits 0-1 are player 0's hand and
                             bits 2-3 are player 1's hand

Hands use the same numbering as the lobby: 1 scissors, 2 rock, 3 paper.
"""

import io
import logging
import struct

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants
from game.edo import structs
from ui.base_ui import HorizontalMenu

logger = logging.getLogger(__name__)

SCISSORS = 1
ROCK = 2
PAPER = 3

# hand -> the hand it beats
BEATS = {SCISSORS: PAPER, ROCK: SCISSORS, PAPER: ROCK}


def hand_name(hand):
    return {SCISSORS: _("scissors"), ROCK: _("rock"), PAPER: _("paper")}.get(hand, _("nothing"))


@utils.duel_message_handler(message_constants.MSG_ROCK_PAPER_SCISSORS)
def msg_rock_paper_scissors(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    rock_paper_scissors(client, player)


def rock_paper_scissors(client, player):
    if player != client.what_player_am_i:
        utils.output(_("Your opponent is choosing rock, paper or scissors."), priority=speech.Priority.INFO)
        return
    menu = HorizontalMenu(_("Rock Paper Scissors"))
    menu.append_item(_("Rock"), lambda: send_hand(client, ROCK))
    menu.append_item(_("Paper"), lambda: send_hand(client, PAPER))
    menu.append_item(_("Scissors"), lambda: send_hand(client, SCISSORS))
    utils.get_ui_stack().push_ui(menu)


def send_hand(client, hand):
    utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack('<i', hand))


@utils.duel_message_handler(message_constants.MSG_HAND_RES)
def msg_hand_res(client, data, data_length):
    data = io.BytesIO(data[1:])
    packed = client.read_u8(data)
    hand_result(client, packed & 0x3, (packed >> 2) & 0x3)


def hand_result(client, hand0, hand1):
    you = client.what_player_am_i if client.what_player_am_i in (0, 1) else 0
    mine, theirs = (hand0, hand1) if you == 0 else (hand1, hand0)
    logger.debug("Hand result: yours=%s, opponent=%s", mine, theirs)
    summary = _("You chose {yours}, your opponent chose {theirs}.").format(
        yours=hand_name(mine), theirs=hand_name(theirs)
    )
    if mine == theirs:
        outcome = _("It's a tie.")
    elif BEATS.get(mine) == theirs:
        outcome = _("You won.")
    else:
        outcome = _("You lost.")
    utils.output(f"{summary} {outcome}", priority=speech.Priority.CRITICAL)
