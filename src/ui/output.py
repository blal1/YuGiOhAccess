"""Screen reader backend.

This is the only output backend; the former ``ui/output2.py`` was an unused
second copy of the same idea and has been folded in here.

``accessible_output3`` drives every platform except macOS, where VoiceOver is
spoken through a long lived ``osascript -i`` process instead.
"""

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


class VoiceOverOutput:
    """Speak through VoiceOver using a persistent osascript process."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            instance = super().__new__(cls)
            instance.process = subprocess.Popen(["osascript", "-i"], stdin=subprocess.PIPE)
            cls._instance = instance
        return cls._instance

    @staticmethod
    def _escape(message):
        # AppleScript string literals only understand backslash escapes, so a
        # card name containing a quote would otherwise break the command.
        return str(message).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")

    def output(self, message, interrupt=False):
        command = f'tell application "VoiceOver" to output "{self._escape(message)}"\n'
        try:
            self.process.stdin.write(command.encode("utf-8"))
            self.process.stdin.flush()
        except (BrokenPipeError, ValueError, OSError):
            logger.exception("VoiceOver output process is no longer usable")


def _create_output():
    if platform.system() == "Darwin":
        return VoiceOverOutput()
    from accessible_output3.outputs import auto

    return auto.Auto()


output = _create_output()
