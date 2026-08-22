import io

from core import utils
from core.i18n import _
from game.card import card_constants
from ui.duel_messages.announce_attrib import show_announce_value_menu, _available_values


@utils.duel_message_handler(140)
def msg_announce_race(client, data, length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u8(data)
    available = client.read_u32(data)
    announce_race(client, player, count, available)


def announce_race(client, player, count, available):
    options = _available_values(
        available,
        card_constants.RACES_OFFSET,
        card_constants.AMOUNT_RACES,
        _("Race {number}"),
    )
    show_announce_value_menu(client, _("Select race"), count, options)
