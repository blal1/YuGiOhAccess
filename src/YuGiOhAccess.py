import sys
import os
import subprocess
from pathlib import Path


def relaunch_in_venv_if_needed():
    if getattr(sys, "frozen", False):
        return
    project_root = Path(__file__).resolve().parent.parent
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return
    if sys.prefix != sys.base_prefix:
        return
    subprocess.Popen([str(venv_python), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=project_root)
    os._exit(0)


relaunch_in_venv_if_needed()

import logging
import wx
from ui import fatal_exception_ui
from ui.app import YuGiOhAccessAPP
from ui.frame import YuGiOhAccessFrame
from core import variables
from core import utils
from core import i18n
from game.language_handler import LanguageHandler
from core.exceptions import LanguageException


def main():
    app = YuGiOhAccessAPP()
    # attach exception hook
    fatal_exception_ui.attach_exception_hook()
    variables.LOCAL_DATA_DIR = variables.EXECUTABLE_DIR / "data"
    utils.setup()
    logger = logging.getLogger(__name__)
    logger.info("Starting YuGiOhAccess")
    utils.log_debug_info()
    utils.parse_dev_options()
    logger.info("Loading config")
    variables.config.load(Path(variables.APP_DATA_DIR) / "config.json")
    variables.config.save(Path(variables.APP_DATA_DIR) / "config.json")
    logger.info("Initializing UI translations")
    i18n.setup()
    logger.info("Loading languages")
    variables.LANGUAGE_HANDLER = LanguageHandler()
    variables.LANGUAGE_HANDLER.add_available_languages()
    if not variables.LANGUAGE_HANDLER.is_loaded("english"):
        variables.LANGUAGE_HANDLER.add("english", "en")
    card_language = variables.config.get("language", "english")
    if not variables.LANGUAGE_HANDLER.is_loaded(card_language):
        card_language = "english"
        variables.config.set("language", card_language)
    try:
        variables.LANGUAGE_HANDLER.set_primary_language(card_language)
    except LanguageException as e:
        logger.error("Failed to set primary language: "+str(e))
        sys.exit(1)
    frame = YuGiOhAccessFrame(None, wx.ID_ANY, "YuGiOhAccess")
    app.SetTopWindow(frame)
    logger.info("Showing frame")
    frame.Show()
    logger.info("Starting main loop")
    app.MainLoop()
    logger.info("Main loop ended, cleaning up")
    if variables.DISCORD_PRESENCE_MANAGER:
        variables.DISCORD_PRESENCE_MANAGER.stop()
        variables.DISCORD_PRESENCE_MANAGER.join()

SCRIPT="""
tell application "VoiceOver"                                                                                                         
    output ""                                                                                                                        
end tell                                                                                                                             
 """

if __name__ == '__main__':
    # so run this script until the permission error comes up.
    # basically only way to do this, is to run it in a loop with subprocess.Popen, and when it takes more than 2 seconds to respond, we know the permission dialog has been szhown.
    # then we can break out
    if sys.platform == "darwin":
        import subprocess
        import time
        while True:
            vo_process = subprocess.Popen(["osascript", "-e", SCRIPT])
            # if the process hasn't stopped after 2 second, then break out of the loop (permission dialog has been shown)
            time.sleep(2)
            if vo_process.poll() is None:
                break
    main()
 
