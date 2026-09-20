from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_REVERSE_DECK)
def msg_reversedeck(client, data, data_length):
    utils.output(_("all decks are now reversed."))

