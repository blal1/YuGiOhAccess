import io

from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_PAY_LPCOST)
def msg_pay_lpcost(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    cost = client.read_u32(data)
    pay_lpcost(client, player, cost)

def pay_lpcost(client, player, cost):
    if player == client.what_player_am_i:
        new_lp = client.player.lifepoints - cost
        utils.output(_("You paid %d LP, now %d") % (cost, new_lp))
        client.player.update_lifepoints(new_lp)
    else:
        new_lp = client.player.opponent_lifepoints - cost
        utils.output(_("Your opponent paid %d LP, now %d") % (cost, new_lp))
        client.player.update_lifepoints(new_lp, True)
