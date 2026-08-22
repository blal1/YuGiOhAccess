import io
import logging

from core import utils
from core.i18n import _
from game.card.card import Card

logger = logging.getLogger(__name__)


@utils.duel_message_handler(25)
def msg_confirm_decktop(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u32(data)
    cards = []
    for i in range(count):
        code = client.read_u32(data)
        controller = client.read_u8(data)
        location = client.read_u8(data)
        sequence = client.read_u32(data)
        if code != 0:
            cards.append(Card(code))
    if player == client.what_player_am_i:
        card_names = ", ".join(c.get_name() for c in cards)
        utils.output(_("Top of your deck: {cards}").format(cards=card_names))
    else:
        utils.output(_("Your opponent checked the top {count} card(s) of their deck.").format(count=count))
