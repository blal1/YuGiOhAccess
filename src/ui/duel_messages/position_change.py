import io

from game.card.card import Card
from game.card import card_constants

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(53)
def msg_pos_change(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    card = Card(code)
    card.controller = client.read_u8(data)
    card.location = card_constants.LOCATION(client.read_u8(data))
    # yes in this message, the sequence is a u8
    card.sequence = client.read_u8(data)
    prevpos = card_constants.POSITION(client.read_u8(data))
    card.position = card_constants.POSITION(client.read_u8(data))
    position_change(client, card, prevpos)

def position_change(client, card, prevpos):
    _player = ""
    if card.controller == client.what_player_am_i:
        _player = "your "
    else:
        _player = "your opponent"
    previous_position_str = prevpos.name.replace("_", " ").lower()
    new_position_str = card.position.name.replace("_", " ").lower()
    utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s %s changes position from %s to %s") % (_player, card.get_name(), previous_position_str, new_position_str)))
    newpos =card.position
    if prevpos == card_constants.POSITION.FACE_DOWN and newpos == card_constants.POSITION.FACE_UP:
        utils.get_ui_stack().play_duel_sound_effect("switch_flip")
    elif prevpos == card_constants.POSITION.FACE_UP and newpos == card_constants.POSITION.FACE_DOWN:
        utils.get_ui_stack().play_duel_sound_effect("switch_facedown")
    elif newpos == card_constants.POSITION.FACE_UP_ATTACK:
        utils.get_ui_stack().play_duel_sound_effect("switch_attack")
    elif newpos == card_constants.POSITION.FACE_UP_DEFENSE:
        utils.get_ui_stack().play_duel_sound_effect("switch_defense")
