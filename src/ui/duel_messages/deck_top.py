import io

from game.card.card import Card
from game.card import card_constants

from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_CONFIRM_DECKTOP)
def msg_confirm_decktop(client, data, data_length):
    cards = []
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    for i in range(count):
        code = client.read_u32(data)
        if code & 0x80000000:
            code = code ^ 0x80000000 # don't know what this actually does
        card = Card(code)
        card.controller = client.read_u8(data)
        card.location = card_constants.LOCATION(client.read_u8(data))
        card.sequence = client.read_u32(data)
        cards.append(card)
    confirm_decktop(client, player, cards)

@utils.duel_message_handler(message_constants.MSG_DECK_TOP)
def msg_decktop(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    client.read_u32(data) # don't know what this number does
    code = client.read_u32(data)
    if code & 0x80000000:
        code = code ^ 0x80000000 # don't know what this actually does
    position = client.read_u32(data)
    card = Card(code)
    card.position = card_constants.POSITION(position)
    decktop(client, player, card)

def decktop(client, player, card):
    if player == client.what_player_am_i:
        utils.output(_("you reveal your top deck card to be %s")%(card.get_name()))
    else:
        utils.output(_("Your opponent reveals their top deck card to be %s")%(card.get_name()))

def confirm_decktop(client, player, cards):
    if player == client.what_player_am_i:
        utils.output(_("you reveal the following cards from your deck:"))
    else:
        utils.output(_("Your opponent reveals the following cards from their deck:"))
    for i, c in enumerate(cards):
        utils.output(_("{index}: {name}").format(index=i + 1, name=c.get_name()))
