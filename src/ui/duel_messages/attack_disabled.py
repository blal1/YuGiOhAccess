from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_ATTACK_DISABLED)
def msg_attack_disabled(client, data, data_length):
    utils.output(_("Attack cancelled"))
    utils.get_ui_stack().play_duel_sound_effect("phase/damage")
    

