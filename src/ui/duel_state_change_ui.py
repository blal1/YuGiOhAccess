import logging
import wx

from core import utils
from core.i18n import _

from game.edo import structs

from ui import server_ui
from ui import replay_ui
from ui import match_ui

logger = logging.getLogger(__name__)

@utils.packet_handler(structs.ServerIdType.DUEL_START)
def handle_duel_start(client, packet_data, packet_length):
    utils.output(_("Duel Starting"))
    if match_ui.is_match(client):
        utils.output(match_ui.score_text(client))
    utils.get_ui_stack().clear_ui_stack()
    utils.get_discord_presence_manager().update_presence(
        state=_("Duel Starting")
    )

@utils.packet_handler(structs.ServerIdType.DUEL_END)
def handle_duel_end(client, packet_data, packet_length):
    utils.output(_("Duel ended"))
    replay_ui.finish_replay_recording(client)
    utils.get_ui_stack().music_audio_manager.fade_out_all_audio()
    if match_ui.is_match(client) and not match_ui.is_match_over(client):
        utils.output(_("Waiting for side decking before the next game."))
        wx.CallLater(400, utils.get_ui_stack().clear_ui_stack)
        return
    wx.CallLater(400, wx.GetApp().GetTopWindow().play_main_music)
    wx.CallLater(400, utils.get_ui_stack().clear_ui_stack)
    wx.CallLater(750, server_ui.server_selection_menu)

@utils.packet_handler(structs.ServerIdType.NEW_REPLAY)
def handle_new_replay(client, packet_data, packet_length):
    logger.debug("New Replay")
    logger.debug(packet_data)
    replay_file = replay_ui.save_replay_packet(client, packet_data, new=True)
    utils.output(_("Replay recording started: {name}").format(name=replay_file.name))
    

@utils.packet_handler(structs.ServerIdType.REPLAY)
def handle_replay(client, packet_data, packet_length):
    logger.debug("Replay")
    logger.debug(packet_data)
    replay_file = replay_ui.save_replay_packet(client, packet_data)
    logger.debug("Replay saved to %s", replay_file)
