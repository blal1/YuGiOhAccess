"""MSG_SHOW_HINT and MSG_AI_NAME: free text the card scripts send.

``Debug.ShowHint`` is how scripts explain a rule or a scripted scenario, and
``Debug.SetAIName`` names the bot in single player. Both use the same encoding:

    u16 length, length bytes of UTF-8, one trailing NUL byte
"""

import io
import logging

from core import speech
from core import utils
from core.i18n import _
from game.edo import message_constants

logger = logging.getLogger(__name__)


def read_string(client, data):
    length = client.read_u16(data)
    raw = data.read(length)
    return raw.decode("utf-8", errors="replace").rstrip("\x00")


@utils.duel_message_handler(message_constants.MSG_SHOW_HINT)
def msg_show_hint(client, data, data_length):
    data = io.BytesIO(data[1:])
    show_hint(client, read_string(client, data))


def show_hint(client, text):
    if not text:
        return
    utils.output(_("Hint: {text}").format(text=text), priority=speech.Priority.INFO)


@utils.duel_message_handler(message_constants.MSG_AI_NAME)
def msg_ai_name(client, data, data_length):
    data = io.BytesIO(data[1:])
    name = read_string(client, data)
    logger.debug("AI name: %s", name)
    if not name:
        return
    client.memory.ai_name = name
    utils.output(_("You are duelling {name}.").format(name=name), priority=speech.Priority.AMBIENT)
