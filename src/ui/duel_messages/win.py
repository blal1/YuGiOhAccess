import io
import logging

from core import utils
from core.i18n import _
from core import variables
from ui import match_ui

logger = logging.getLogger(__name__)

@utils.duel_message_handler(5)
def msg_win(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    reason = client.read_u8(data)
    win(client, player, reason)

def win(client, player, reason):
    logger.debug("Win: %d %d", player, reason)
    if player == 2:
        utils.output(_("You and your opponent ended the duel in a draw."))
        _announce_match_result(client, player)
        return

    def l_reason():
        return variables.LANGUAGE_HANDLER.strings['victory'][reason]

    if player == client.what_player_am_i:
        utils.output(_("You win the duel! {reason}").format(reason=l_reason()))
    else:
        utils.output(_("You lose the duel! {reason}").format(reason=l_reason()))
    _announce_match_result(client, player)

    # clear out stuff from the client
    client.duel_field = None
    client.player = None
    client.turn_count = 0
    client.has_announced_turn_order = False
    client.current_phase = ""
    client._what_player_am_i = -1
    client.is_it_my_turn = False


def _announce_match_result(client, player):
    state = match_ui.record_duel_result(client, player)
    if not state:
        return
    utils.output(match_ui.score_text(client))
    if match_ui.is_match_over(client):
        if state["player_wins"] > state["opponent_wins"]:
            utils.output(_("You win the match."))
        else:
            utils.output(_("You lose the match."))
    else:
        utils.output(_("Prepare to side deck for the next game."))
