import threading
import time
import logging
import platform
import sys
import textwrap
import traceback
from pathlib import Path
import wx
import wx.lib.dialogs

from core import variables
from core.i18n import _
from ui.audio import AudioManager

def attach_exception_hook():
    if not variables.IS_FROZEN:
        sys.excepthook = _custom_exception_hook
    else:
        sys.excepthook = _custom_exception_hook_frozen

def _custom_exception_hook_frozen(exception_type, value, tb):
    logger = logging.getLogger(__name__)
    logger.error("Unhandled exception occurred", exc_info=(exception_type, value, tb))
    thread = threading.Thread(target=_play_error_sound, daemon=True)
    thread.start()
    
def _play_error_sound():
    audio_manager = AudioManager("error_sound_effects_volume")
    audio_manager.play_audio("error.wav")
    time.sleep(2)

def _custom_exception_hook(exception_type, value, tb):
    logger = logging.getLogger(__name__)
    logger.error("Unhandled exception occurred", exc_info=(exception_type, value, tb))
    log_content = _retrieve_log_content()
    tb_text = "".join(traceback.format_tb(tb)).strip()
    message = textwrap.dedent(
        _("Unhandled exception occurred. Please report this to the developers, and attach the information in this dialog:")
        + f"""

    Traceback:
    {tb_text}
    {str(exception_type)}, {value}

    System information:
    OS: {platform.platform()} {platform.system_alias(platform.system(), platform.release(), platform.version())}
    Python: {platform.python_version()} {platform.python_compiler()} {platform.python_implementation()}
    Architecture: {platform.architecture()}
    Processor: {platform.processor()}

    Log content:
    {log_content}
                            """).replace("  ", "")

    dlg = wx.lib.dialogs.ScrolledMessageDialog(None, message, _("Unhandled exception"))
    dlg.ShowModal()
    dlg.Destroy()

def _retrieve_log_content():
    """Check if the logfile exists. If it does, return its contents, if it doesn't, return log not available."""
    try:
        return Path(variables.LOG_FILE).read_text()
    except FileNotFoundError:
        return _("Log not available")
