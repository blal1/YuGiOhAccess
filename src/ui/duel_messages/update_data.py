import io
import logging

from game.card import card_constants

from core import utils
from core.i18n import _

logger = logging.getLogger(__name__)

@utils.duel_message_handler(6)
def msg_update_data(client, data, length):
    # the first byte is the message id, so we skip it
    # the second byte is empty for this message
    data = io.BytesIO(data[1:])
    con = client.read_u8(data)
    loc = client.read_u8(data)
    bufsize = client.read_u32(data)
    queries = parse_queries(client, con, loc, bufsize, data)
    return update_data(client, con, loc, queries)

class QueryResult:
    def __init__(self):
        # Use super() to avoid recursion in __setattr__
        super().__setattr__('fields', {'flags': card_constants.QUERY(0)})
    
    def __getattr__(self, name):
        try:
            return self.fields[name]
        except KeyError:
            # You might want to raise an AttributeError instead
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def __setattr__(self, name, value):
        # Use super() to avoid recursion in __setattr__
        if name == 'fields':
            super().__setattr__(name, value)
        else:
            self.fields[name] = value

    def __repr__(self):
        return f"<QueryResult {self.fields}>"

def parse_queries(client, controller, location, size, data):
    queries = []
    query = QueryResult()
    while size > 0:
        start = data.tell()
        query_size = client.read_u16(data)
        if query_size == 0:
            query.onfield_skipped = True
            size -= data.tell() - start
            queries.append(query)
            query = QueryResult()
            continue

        flags = card_constants.QUERY(client.read_u32(data))
        query.flags |= flags
        query.onfield_skipped = False

        if flags & card_constants.QUERY.CODE:
            query.code = client.read_u32(data)
        if flags & card_constants.QUERY.POSITION:
            query.position = client.read_u32(data)
            query.controller = controller
            query.location = location
            query.sequence = len(queries) & 0xff
        if flags & card_constants.QUERY.ALIAS:
            query.alias = client.read_u32(data)
        if flags & card_constants.QUERY.TYPE:
            query.type = client.read_u32(data)
        if flags & card_constants.QUERY.LEVEL:
            query.level = client.read_u32(data)
        if flags & card_constants.QUERY.RANK:
            query.rank = client.read_u32(data)
        if flags & card_constants.QUERY.ATTRIBUTE:
            query.attribute = client.read_u32(data)
        if flags & card_constants.QUERY.RACE:
            query.race = (client.read_u32(data) << 32) + client.read_u32(data)
        if flags & card_constants.QUERY.ATTACK:
            query.attack = client.read_u32(data)
        if flags & card_constants.QUERY.DEFENSE:
            query.defense = client.read_u32(data)
        if flags & card_constants.QUERY.BASE_ATTACK:
            query.base_attack = client.read_u32(data)
        if flags & card_constants.QUERY.BASE_DEFENSE:
            query.base_defense = client.read_u32(data)
        if flags & card_constants.QUERY.REASON:
            query.reason = client.read_u32(data)
        if flags & card_constants.QUERY.COVER:
            query.cover = client.read_u32(data)
        if flags & card_constants.QUERY.REASON_CARD:
            size = client.read_u16(data)
            query.reason_card = {}
            if size:
                query.reason_card['controler'] = client.read_u8(data)
                query.reason_card['location'] = client.read_u8(data)
                query.reason_card['sequence'] = client.read_u32(data)
                query.reason_card['position'] = client.read_u32(data)
            else:
                # Skip the unused bytes
                client.read_u64(data)
        if flags & card_constants.QUERY.EQUIP_CARD:
            size = client.read_u16(data)
            query.equip_card = {}
            if size:
                query.equip_card['controler'] = client.read_u8(data)
                query.equip_card['location'] = client.read_u8(data)
                query.equip_card['sequence'] = client.read_u32(data)
                query.equip_card['position'] = client.read_u32(data)
            else:
                # Skip the unused bytes
                client.read_u64(data)
        if flags & card_constants.QUERY.TARGET_CARD:
            query.target_card_size = client.read_u16(data)
            query.target_card_count = client.read_u32(data)
            query.target_cards = []
            for _ in range(query.target_card_count):
                controler = client.read_u8(data)
                location = client.read_u8(data)
                sequence = client.read_u32(data)
                position = client.read_u32(data)
                query.target_cards.append((controler, location, sequence, position))
        if flags & card_constants.QUERY.OVERLAY_CARD:
            query.overlay_card_size = client.read_u16(data)
            query.overlay_card_count = client.read_u32(data)
            query.overlay_cards = []
            for _ in range(query.overlay_card_count):
                card_code = client.read_u32(data)
                query.overlay_cards.append(card_code)
        if flags & card_constants.QUERY.COUNTERS:
            _ = client.read_u16(data)
            query.counters_count = client.read_u32(data)
            query.counters = []
            for _ in range(query.counters_count):
                counter_data = client.read_u32(data)
                query.counters.append(counter_data)
        if flags & card_constants.QUERY.OWNER:
            query.owner = client.read_u8(data)
        if flags & card_constants.QUERY.STATUS:
            query.status = client.read_u32(data)
        if flags & card_constants.QUERY.IS_PUBLIC:
            query.is_public = client.read_u8(data)
        if flags & card_constants.QUERY.LSCALE:
            query.lscale = client.read_u32(data)
        if flags & card_constants.QUERY.RSCALE:
            query.rscale = client.read_u32(data)
        if flags & card_constants.QUERY.LINK:
            query.link = client.read_u32(data)
            query.link_marker = client.read_u32(data)
        if flags & card_constants.QUERY.IS_HIDDEN:
            query.is_hidden = client.read_u8(data)

        if flags & card_constants.QUERY.END:
            queries.append(query)
            query = QueryResult()

        if data.tell() - start != query_size + 2:
            raise RuntimeError(f"Query doesn't match size {query_size} flags 0x{flags:X} start {start} cur {data.tell()}")
        
        size -= data.tell() - start

    return queries

def update_data(client, controller, location, queries):
    # check for start of duel condition, and reinstantiate the field
    if client.turn_count == 0 and not client.has_announced_turn_order:
        utils.output(_("You are going first")) if controller == 0 else utils.output(_("You are going second"))
        client.what_player_am_i = controller
        client.has_announced_turn_order = True
    client.get_duel_field().update_field(client, controller, location, queries)


