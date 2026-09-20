from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_DAMAGE_STEP_START)
def msg_begin_damage(client, data, data_length):
    utils.output(_("begin damage"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damage")
    

