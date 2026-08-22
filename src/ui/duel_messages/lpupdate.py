import io
import wx
from core import utils

@utils.duel_message_handler(94)
def msg_lpupdate(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    lp = client.read_u32(data)
    lpupdate(client, player, lp)
 
def lpupdate(client, player, lp):
    if player == client.what_player_am_i:
        lpsource = client.player.update_lifepoints(lp)
    else:
        lpsource = client.player.update_lifepoints(lp, True)
    # this is a special case
    while lpsource in utils.get_ui_stack().sound_effects_audio_manager.sources.values():
        wx.Yield()
    # if the lp that was updated are 0 or less, play lpzero. If not play lpend.
    if lp <= 0:
        utils.get_ui_stack().play_duel_sound_effect("lpzero")
    else:
        utils.get_ui_stack().play_duel_sound_effect("lpend")
