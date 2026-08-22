import io

from core import utils
from core.i18n import _

@utils.duel_message_handler(32)
def msg_shuffle_deck(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    shuffle_deck(client, player)
    return data.read()

def shuffle_deck(client, player):
    utils.get_ui_stack().play_duel_sound_effect("shuffle")
    if player == client.what_player_am_i:
        utils.output(_("You shuffled your deck."))
    else:
        utils.output(_("Opponent shuffled their deck."))
