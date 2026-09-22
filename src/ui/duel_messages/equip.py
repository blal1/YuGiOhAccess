import io

from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_EQUIP)
def msg_equip(client, data, data_length):
    data = io.BytesIO(data[1:])
    controller, location, sequence, position = client.read_location(data)
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    card = client.get_card(controller, location, sequence)
    target = client.get_card(target_controller, target_location, target_sequence)
    equip(client, card, target)

def _name_of(card):
    """A card's name, or something to say when the client has not seen it.

    ``get_card`` returns None for a zone we have not been told about, which is
    why this message used to name neither side: guarding the whole sentence
    was easier than guarding each half. Naming what is known is far more use
    than "Card equipped to target."
    """
    if card is None:
        return _("a card")
    get_name = getattr(card, "get_name", None)
    return get_name() if get_name else str(card)


def equip(client, card, target):
    utils.output(
        _("{card} equipped to {target}.").format(
            card=_name_of(card), target=_name_of(target)
        )
    )


