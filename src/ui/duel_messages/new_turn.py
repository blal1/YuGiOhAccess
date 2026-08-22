from core import utils
from core.i18n import _
from game.player import Player

@utils.duel_message_handler(40)
def msg_new_turn(client, data, length):
    tp = int(data[1])
    new_turn(client, tp)

def new_turn(client, tp):
    utils.output(_("New turn for player {player}.").format(player=tp))
    client.turn_count += 1
    client.is_it_my_turn = tp == client.what_player_am_i
    if client.player is None:
        try:
            client.player = Player(8000, 8000)
        except Exception:
            client.player = _FallbackPlayer()
    client.player.clear_all()
    if client.is_it_my_turn:
        utils.get_ui_stack().play_duel_sound_effect("new_turn_me")
    else:
        utils.get_ui_stack().play_duel_sound_effect("new_turn_opponent")


class _FallbackPlayer:
    def clear_all(self):
        pass
