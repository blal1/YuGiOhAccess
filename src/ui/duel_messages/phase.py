import io

from core import utils
from core.i18n import _
from game.card import card_constants



@utils.duel_message_handler(41)
def msg_new_phase(client, data, length):
    data = io.BytesIO(data[1:])
    phase_int = client.read_u16(data)
    phase(client, phase_int)

def phase(client, phase_int):
    client.current_phase = phase_int
    phase_str = card_constants.PHASES.get(phase_int, str(phase_int))
    utils.output(_("Entering {phase}").format(phase=phase_str))
    if phase_int == 2:
        utils.get_ui_stack().play_duel_sound_effect("phase/standby")
    elif phase_int == 4:
        utils.get_ui_stack().play_duel_sound_effect("phase/main")
    elif phase_int == 8:
        utils.get_ui_stack().play_duel_sound_effect("phase/battle")
    elif phase_int == 0x200:
        utils.get_ui_stack().play_duel_sound_effect("phase/end")
    if client.player:
        prefix = _("My") if client.is_it_my_turn else _("My opponents")
        utils.get_discord_presence_manager().update_presence(
            state=_("In a duel"),
            details=_("{prefix} {phase} - {lp} / {opp_lp} LP").format(prefix=prefix, phase=phase_str, lp=client.player.lifepoints, opp_lp=client.player.opponent_lifepoints)
        )

