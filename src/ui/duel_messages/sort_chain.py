import io
import struct

from game.card.card import Card
from game.card import card_constants
from game.edo import structs

from core import utils

@utils.duel_message_handler(21)
def msg_sort_chain(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    size = client.read_u32(data)
    cards = []
    for i in range(size):
        code = client.read_u32(data)
        card = Card(code)
        card.controller = client.read_u8(data)
        card.location = card_constants.LOCATION(client.read_u32(data))
        card.sequence = client.read_u32(data)
        cards.append(card)
    sort_chain(client, player, cards)

def sort_chain(client, player, cards):
    client.send(structs.ClientIdType.RESPONSE, struct.pack('i', -1))

