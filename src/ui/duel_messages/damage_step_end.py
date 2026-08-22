from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(114)
def msg_end_damage(client, data, data_length):
    damage_step_end(client)
    return data[1:]

def damage_step_end(client):
    utils.output(variables.LANGUAGE_HANDLER._("end damage"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damageend")
