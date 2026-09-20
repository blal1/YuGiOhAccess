from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_DAMAGE_STEP_END)
def msg_end_damage(client, data, data_length):
    damage_step_end(client)
    return data[1:]

def damage_step_end(client):
    utils.output(_("end damage"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damageend")
