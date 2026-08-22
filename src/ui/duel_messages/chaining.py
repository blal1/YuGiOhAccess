import io

from core import utils
from core.i18n import _

from game.card.card import Card

@utils.duel_message_handler(70)
def msg_chaining(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    controller, location, sequence, position = client.read_location(data)
    card = Card(code)
    card.set_location_and_position_info(controller, location, sequence, position)
    tc = client.read_u8(data)
    tl = client.read_u8(data)
    ts = client.read_u32(data)
    desc = client.read_u64(data)
    cs = client.read_u32(data)
    chaining(client, card, tc, tl, ts, desc, cs)


def chaining(client, card, triggering_controller, triggering_location, triggering_sequence, desc, chaining_size):
    _player = ""
    if card.controller == client.what_player_am_i:
        _player = "You"
    else:
        _player = "Your opponent"
    description = card.get_effect_description(desc, True)
    message = f"{_player} activating {card.get_name()}"
    if description != '':
        message += '\n' + description
    utils.output(_("{message}").format(message=message))
