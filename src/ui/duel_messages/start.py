import io
import logging
import time


from core import speech
from core import utils
from core.i18n import _
from game.player import Player


from ui import duel_field
from ui.duel_messages import player_hint
from game.edo import message_constants

logger = logging.getLogger(__name__)

# Bits 0-3 of the play type byte hold our own player index, the upper bits mark
# spectators (0x10 and above).
PLAY_TYPE_PLAYER_MASK = 0x0F
PLAY_TYPE_SPECTATOR = 0xF0


@utils.duel_message_handler(message_constants.MSG_START)
def msg_start(client, data, data_len):
    # the first byte is the message id, the second tells us which side we play
    play_type = data[1]
    set_player_index_from_play_type(client, play_type)
    data = io.BytesIO(data[2:])
    lp0 = client.read_u32(data)
    lp1 = client.read_u32(data)
    t0dz = client.read_u16(data)
    t0edz = client.read_u16(data)
    t1dz = client.read_u16(data)
    t1edz = client.read_u16(data)
    # start the duel
    start(client, lp0, lp1, t0dz, t0edz, t1dz, t1edz)

def set_player_index_from_play_type(client, play_type):
    """Record which side of the field we are on.

    This byte is the only authoritative statement the server makes about our
    identity. Ignoring it left the client on whatever room slot it happened to
    be given, so a player who went second read every controller byte from the
    opponent's side and saw both hands mixed together.
    """
    if play_type & PLAY_TYPE_SPECTATOR:
        logger.info("Duel starting as spectator (play type 0x%02X)", play_type)
        return
    player_index = play_type & PLAY_TYPE_PLAYER_MASK
    if player_index not in (0, 1):
        logger.warning("Duel start sent an unusable play type 0x%02X", play_type)
        return
    logger.info("Duel starting as player %d (play type 0x%02X)", player_index, play_type)
    client.what_player_am_i = player_index
    utils.output(_("You are going first")) if player_index == 0 else utils.output(_("You are going second"))
    client.has_announced_turn_order = True


@utils.ui_function
def start(client, lp0, lp1, t0dz, t0edz, t1dz, t1edz):
    # A new duel inherits nothing from the previous one.
    player_hint.reset_player_hints()
    speech.MESSAGE_LOG.clear()
    utils.get_ui_stack().music_audio_manager.fade_out_all_audio()
    time.sleep(0.050)
    # clear the ui stack
    utils.get_ui_stack().clear_ui_stack()
    field = duel_field.DuelField(client)
    client.set_duel_field(field)
    # lp is lifepoints
    # t0 and t1 are team 0 and 1
    # dz is deck size
    # edz is extra deck size
    utils.output(_("Starting lifepoints: {lp0} vs {lp1}").format(lp0=lp0, lp1=lp1))
    client.player = Player(lp0, lp1)
    utils.get_ui_stack().play_duel_sound_effect("start")
    # generate the duel field
    return field

