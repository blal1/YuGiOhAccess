from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(113)
def msg_begin_damage(client, data, data_length):
    utils.output(variables.LANGUAGE_HANDLER._("begin damage"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damage")
    

