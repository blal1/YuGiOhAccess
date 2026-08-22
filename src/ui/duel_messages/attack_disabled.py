from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(112)
def msg_attack_disabled(client, data, data_length):
    utils.output(variables.LANGUAGE_HANDLER._("Attack cancelled"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damage")
    

