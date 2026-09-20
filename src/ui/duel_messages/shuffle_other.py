import io

from core import speech
from core import utils
from core.i18n import _

from game.card import card_constants
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_SHUFFLE_HAND)
def msg_shuffle_hand(client, data, data_length):
    return msg_shuffle_others(client, data, card_constants.LOCATION.HAND)

@utils.duel_message_handler(message_constants.MSG_SHUFFLE_EXTRA)
def msg_shuffle_extra_deck(client, data, data_length):
    return msg_shuffle_others(client, data, card_constants.LOCATION.EXTRA)

def msg_shuffle_others(client, data, location):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    codes = []
    for i in range(count):
        codes.append(client.read_u32(data))
    shuffle_others(client, player, location, count, codes)
    return data.read()

def shuffle_others(client, player, location, count, codes):
    if location == card_constants.LOCATION.EXTRA or location == card_constants.LOCATION.DECK:
        utils.get_ui_stack().play_duel_sound_effect("shuffle")
    location = _("hand") if location == card_constants.LOCATION.HAND else _("extra deck")
    if player == client.what_player_am_i:
        utils.output(_("You shuffled {count} cards in your {location}.").format(count=count, location=location), priority=speech.Priority.AMBIENT)
    else:
        utils.output(_("Opponent shuffled {count} cards in their {location}.").format(count=count, location=location), priority=speech.Priority.AMBIENT)
