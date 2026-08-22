import io
import logging

from core import exceptions
from core import utils

from ui.duel_messages import update_data
from game.card.card import Card

logger = logging.getLogger(__name__)

@utils.duel_message_handler(7)
def msg_update_card(client, data, data_length):
    data = io.BytesIO(data[1:])
    controller = client.read_u8(data)
    location = client.read_u8(data)
    sequence = client.read_u8(data)
    query = update_data.parse_queries(client, controller, location, 1, data)
    update_card(client, controller, location, sequence, query)

def update_card(client, controller, location, sequence, query):
    card = client.get_card(controller, location, sequence)
    if not card:
        raise exceptions.CardNotFoundException("Card not found")
    for update in query:
        apply_query_to_card(card, update)


def apply_query_to_card(card, query):
    if getattr(query, "onfield_skipped", False):
        return card
    for field in (
        "code",
        "alias",
        "type",
        "level",
        "rank",
        "attribute",
        "race",
        "attack",
        "defense",
        "base_attack",
        "base_defense",
        "reason",
        "cover",
        "owner",
        "status",
        "is_public",
        "lscale",
        "rscale",
        "link",
        "link_marker",
        "is_hidden",
        "data",
    ):
        if hasattr(query, field):
            setattr(card, field, getattr(query, field))
    if hasattr(query, "position"):
        card.position = query.position
    if hasattr(query, "rank"):
        card.level = query.rank
    if hasattr(query, "link_marker") and query.link_marker:
        card.defense = query.link_marker
    if hasattr(query, "overlay_cards"):
        card.xyz_materials = [Card(card_code) for card_code in query.overlay_cards]
    return card
