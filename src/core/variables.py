import sys
import ctypes
from datetime import datetime
from pathlib import Path
from appdirs import user_data_dir

from core import dotdict
from core import config
from core import version

from game.edo import structs

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    IS_FROZEN = True
    EXECUTABLE_DIR = Path(sys._MEIPASS)
    BUNDLE_DIR_TO_UPDATE = Path(sys._MEIPASS).parent
else:
    IS_FROZEN = False
    EXECUTABLE_DIR = Path(__file__).parent.parent
    BUNDLE_DIR_TO_UPDATE = EXECUTABLE_DIR

APP_NAME = "YuGiOhAccess"
APP_VERSION = version.VERSION
APP_AUTHOR = "YuGiOhAccess"
APP_DATA_DIR = user_data_dir(APP_NAME, APP_AUTHOR,roaming=True)
DEBUG_MODE = True # set to False before release
LOCAL_DATA_DIR = None
LOG_FILE = Path(APP_DATA_DIR) / "logs" / f"{datetime.now().strftime('%Y-%m-%d %H-%M-%S')}.log"
UPDATER_CACHE_DIR = Path(APP_DATA_DIR) / "updates"
DECK_DIR = Path(APP_DATA_DIR) / "decks"

DEV_OPTIONS = None
config = config.Config({
    "first_time_run": True,
        "nickname": "Player",
        "language": "english",
        "ui_language": "en",
        "sound_effects_volume": 0.6,
        "music_volume": 0.1,
        "error_sound_effects_volume": 0.6,
        "enable_hints": True,
        "screenreader_output_only_on_application_focus": True,
        "helper_zones": True,
        "rock_paper_scissors_bot_behavior": "random",
        "enable_bot_chat": True,
        "ip_cache": {},
        "discord_login": {},
    })

LANGUAGE_HANDLER = None
DISCORD_PRESENCE_MANAGER = None
edo_client_version = structs.ClientVersion(
    (ctypes.c_uint8 * 2)(*([41, 0])),
    (ctypes.c_uint8 * 2)(*([11, 0]))
)

DISCORD_APPLICATION_INFO = dotdict.DotDict()
DISCORD_APPLICATION_INFO.client_id = "1324421529257119885"
DISCORD_APPLICATION_INFO.use_pkce = True
DISCORD_APPLICATION_INFO.redirect_uri = "https://yugiohaccess.com/login/"
DISCORD_APPLICATION_INFO.prompt = "consent"

DATA_REPOSITORIES = [
    {
        "name": "databases",
        "url": "ProjectIgnis/BabelCDB",
        "local_path": Path(APP_DATA_DIR) / "sync" / "databases2",
    },
    {
        "name": "banlists",
        "url": "ProjectIgnis/LFLists",
        "local_path": Path(APP_DATA_DIR) / "sync" / "banlists2",
    },
    {
        "name": "languages",
        "url": "Team13fr/IgnisMulti",
        "local_path": Path(APP_DATA_DIR) / "sync" / "languages",
        "required": False,
    },
]
