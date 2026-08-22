import io

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(91)
def msg_damage(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    amount = client.read_u32(data)
    damage(client, player, amount)

def damage(client, player, amount):
    if player == client.what_player_am_i:
        new_lp = client.player.lifepoints - amount
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Your lp decreased by %d, now %d") % (amount, new_lp)))
        client.player.update_lifepoints(new_lp)
    else:
        new_lp = client.player.opponent_lifepoints - amount
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("Your opponent's lp decreased by %d, now %d") % (amount, new_lp)))
        client.player.update_lifepoints(new_lp, True)
