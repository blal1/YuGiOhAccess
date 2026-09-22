from pathlib import Path
import logging
import random

from ui import data_updater_ui
import wx
import wx.adv

from ui import output
from ui import main_ui
from core import speech
from core import utils
from core import variables
from core.i18n import _
from ui.audio import AudioManager

logger = logging.getLogger(__name__)

class YuGiOhAccessFrame(wx.Frame):
    def __init__(self, parent=None, id=-1, title="YuGiOhAccess"):
        logger.info("Initializing screenreader output")
        self.sr_output = output.output

        # init audio output
        logger.info("Initializing audio output")
        self.sound_effects_audio_manager = AudioManager("sound_effects_volume")
        self.music_audio_manager = AudioManager("music_volume")

        logger.info("Initializing frame")
        wx.Frame.__init__(self, parent, id, title)

        self.menubar = wx.MenuBar()
        self.file_menu = wx.Menu()
        self.about_menu_item = self.file_menu.Append(wx.ID_ABOUT, _("&About"), _("Information about this program"))
        self.Bind(wx.EVT_MENU, self.on_about, self.about_menu_item)
        self.exit_menu_item = self.file_menu.Append(wx.ID_EXIT, _("E&xit"), _("Terminate the program"))
        self.Bind(wx.EVT_MENU, self.on_exit, self.exit_menu_item)
        self.menubar.Append(self.file_menu, _("&File"))
        self.SetMenuBar(self.menubar)
 
        self.game_area = wx.Panel(self, name="Game Area")

        self.ui_stack = []

        # make a sizer for the game area and the input/output sizer, where the game area is to the left of the input/output sizer, and takes up 2/3 of the space
        self.main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.main_sizer.Add(self.game_area, 1, wx.EXPAND)

        self.SetSizer(self.main_sizer)

        # make the panel take up the whole window
        self.game_area.Fit()

        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.Bind(wx.EVT_CLOSE, self.on_close)


        # max size of the window
        self.Maximize(True)
        # show
        self.Show(True)
        self.play_main_music()

        data_updater_ui.ensure_yugioh_data_is_up_to_date()
        self.ui_stack[-1].SetFocus()


    def push_ui(self, ui):
        logger.info(f"Pushing ui {ui}")
        logger.debug(f"Current ui stack: {self.prettify_ui_stack()}")
        if self.ui_stack:
            self.main_sizer.Hide(self.ui_stack[-1])
            self.ui_stack[-1].Hide()
        else:
            self.main_sizer.Hide(self.game_area)
            self.game_area.Hide()
        self.ui_stack.append(ui)
        # update the self.game_area in the sizer to be this panel instead
        self.main_sizer.Add(ui, 2, wx.EXPAND)
        ui.Show()
        ui.SetFocus()
        self.Fit()

    def pop_ui(self):
        if len(self.ui_stack) == 0:
            return
        old_ui= self.ui_stack.pop()
        # remove from size
        if old_ui:
            self.main_sizer.Hide(old_ui)
            old_ui.Hide()
            old_ui.Close()
        # if there are still ui elements in the stack, set focus to the last one
        if len(self.ui_stack) > 0:
            self.ui_stack[-1].Show()
            self.main_sizer.Show(self.ui_stack[-1])
            self.ui_stack[-1].SetFocus()
        else:
            self.game_area.Show()
            self.main_sizer.Show(self.game_area)
        self.Layout()
        self.Fit()

    def remove_ui(self, ui):
        """Remove one screen from the stack, wherever it happens to sit.

        pop_ui only removes the top, which is not good enough during a duel: a
        duel message can push its own screen while a prompt is open, and popping
        then discards the wrong one and leaves the prompt stranded.
        """
        if ui not in self.ui_stack:
            return False
        was_top = self.ui_stack[-1] is ui
        self.ui_stack.remove(ui)
        self.main_sizer.Hide(ui)
        ui.Hide()
        if was_top:
            if self.ui_stack:
                self.ui_stack[-1].Show()
                self.main_sizer.Show(self.ui_stack[-1])
                self.ui_stack[-1].SetFocus()
            else:
                self.game_area.Show()
                self.main_sizer.Show(self.game_area)
        try:
            ui.Destroy()
        except RuntimeError:
            logger.debug("UI %s was already destroyed", ui)
        self.Layout()
        self.Fit()
        return True

    def clear_ui_stack(self):
        while len(self.ui_stack) > 0:
            self.pop_ui()

    def refresh_ui(self, ui_function=None):
        """Build the current screen again.

        With no builder the screen's own ``rebuild`` is used, which
        ``utils.ui_function`` puts there when the screen is first pushed.
        The builder replaces the current screen itself, so nothing is popped
        here: doing both threw away the screen underneath as well.
        """
        logger.info("Refreshing ui")
        logger.debug(f"Current ui stack: {self.prettify_ui_stack()}")
        if ui_function is None:
            ui_function = getattr(self.ui_stack[-1], "rebuild", None) if self.ui_stack else None
        if ui_function is None:
            logger.warning("Nothing to refresh: the current screen does not know how it was built")
            return
        ui_function()

    def get_main_ui(self):
        return  main_ui.main_menu_view()
    
    def prettify_ui_stack(self):
        return [str(ui) for ui in self.ui_stack]



    def on_about(self, event):
        info = wx.adv.AboutDialogInfo()
        info.SetName("YuGiOhAccess")
        info.SetVersion(utils.version_string_to_pretty(variables.APP_VERSION))
        info.SetDescription(_("An accessible client for playing Yu-Gi-Oh! online"))
        info.SetDevelopers(["Jessica Tegner", _("YuGiOhAccess contributors")])
        info.SetWebSite("https://YuGiOhAccess.com", _("YuGiOhAccess Website"))
        info.SetCopyright("Copyright (c) 2024 YuGiOhAccess")
        info.SetLicence("""GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007

                        YuGiOhAccess is free software: you can redistribute it and/or modify
                        it under the terms of the GNU General Public License as published by
                        the Free Software Foundation, either version 3 of the License, or
                        (at your option) any later version.
                        """)
        wx.adv.AboutBox(info)

    def on_exit(self, event):
        self.Close()

    def on_close(self, event):
        logger.info("Closing frame")
        if self.sound_effects_audio_manager:
            self.sound_effects_audio_manager.stop_all_audio()
        if self.music_audio_manager:
            self.music_audio_manager.stop_all_audio()
        event.Skip()

    def play_random_duel_sound_effect_in_directory(self, directory_name, x=0.0, y=0.0, z=0.0):
        # pick a random file from the data/sounds/duel/directory_name folder and play it
        sound_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "duel" / directory_name).iterdir())
        # remove any that doesn't end with .flac, .wav,, .ogg or .opus
        sound_files = [file for file in sound_files if file.suffix in {".flac", ".wav", ".ogg", ".opus"}]
        random_sound_file = random.choice(sound_files)
        # keep in mind that the file is in duel/directory_name/random_sound_file.name
        self.sound_effects_audio_manager.play_audio(f"duel/{directory_name}/{random_sound_file.name}", x=x, y=y, z=z) 

    # Effects we have already reported as missing, so each is logged once.
    _missing_sound_effects: set = set()

    def play_duel_sound_effect(self, effect, x=0.0, y=0.0, z=0.0):
        # so the full path to the specific sound effect is sounds/duel/effect, .flac, .wav, .ogg or .opus
        resolved_file_path = None
        for extension in {".flac", ".wav", ".ogg", ".opus"}:
            file_path = Path(variables.LOCAL_DATA_DIR / "sounds" / "duel" / f"{effect}{extension}")
            if file_path.exists():
                resolved_file_path = file_path
                break
        if not resolved_file_path:
            # Once per effect, not once per event: a missing phase sound was
            # filling the log with the same line dozens of times a duel and
            # burying everything else.
            if effect not in self._missing_sound_effects:
                self._missing_sound_effects.add(effect)
                logger.warning(
                    "Sound effect %s has no file in %s (looked for .flac, .wav, .ogg, .opus)",
                    effect, Path(variables.LOCAL_DATA_DIR) / "sounds" / "duel",
                )
            return
        self.sound_effects_audio_manager.play_audio(f"duel/{effect}{resolved_file_path.suffix}", x=x, y=y, z=z)

    def play_main_music(self):
        # pick a random file from the data/sounds/music/start folder and play it
        music_files = list(Path(variables.LOCAL_DATA_DIR / "sounds" / "music" / "start").iterdir())
        random_music_file = random.choice(music_files)
        # keep in mind that the file is in music/start/random_music_file.name
        self.music_audio_manager.play_audio(f"music/start/{random_music_file.name}", looping=True)

    def output(self, text, interrupt=False):
        self.sr_output.output(text, interrupt) # Assume this is some function for outputting text



    def on_key_down(self, event):
        keycode = event.GetKeyCode()
        # f5 and f6 are used for sound effect volume
        # f7 and f8 are used for music volume
        if keycode == wx.WXK_F5:
            self.sound_effects_audio_manager.decrease_volume()
        elif keycode == wx.WXK_F6:
            self.sound_effects_audio_manager.increase_volume()
        elif keycode == wx.WXK_F7:
            self.music_audio_manager.decrease_volume()
        elif keycode == wx.WXK_F8:
            self.music_audio_manager.increase_volume()
        # F9 replays what was said recently, including anything that arrived
        # while the window was in the background and could not be spoken.
        elif keycode == wx.WXK_F9:
            count = speech.DEFAULT_REPLAY_COUNT if not event.ShiftDown() else len(speech.MESSAGE_LOG)
            utils.replay_recent_messages(count)
        event.Skip()
