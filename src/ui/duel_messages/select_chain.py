import io
import logging
import struct

import wx

from core import utils
from core.i18n import _

from game.card.card import Card
from game.card.location_conversion import LocationConversion
from game.edo import structs
from game.edo import message_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(message_constants.MSG_SELECT_CHAIN)
def msg_select_chain(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    spe_count = client.read_u8(data)
    forced = client.read_u8(data)
    hint_timing = client.read_u32(data)
    other_timing = client.read_u32(data)
    size = client.read_u32(data)
    # print out what we got so far
    logger.debug(f"Player: {player}, Special count: {spe_count}, Forced: {forced}, Hint timing: {hint_timing}, Other timing: {other_timing}, Size: {size}")
    chains = []
    for i in range(size):
        code = client.read_u32(data)
        logger.debug(f"Code: {code}")
        controller, loc, sequence, position = client.read_location(data)
        card = Card(code)
        card.set_location_and_position_info(controller, loc, sequence, position)
        desc = client.read_u64(data)
        logger.debug(f"Description: {desc}")
        et = client.read_u8(data)
        logger.debug(f"Effect type: {et}")
        chains.append((et, card, desc))
    select_chain(client, player, size, spe_count, forced, chains)

def select_chain(client, player, size, spe_count, forced, chains):
    if size == 0 and spe_count == 0:
        logger.debug("empty chain")
        client.send(structs.ClientIdType.RESPONSE, struct.pack('i', -1))
        return
    if player != client.what_player_am_i:
        utils.output(_("Opponent is selecting chain"))
        return
    logger.debug(f"Player {player} is selecting chain, size: {size}, spe_count: {spe_count}, forced: {forced}")
    chain_cards = []
    for i in range(size):
        et, card, desc = chains[i]
        card.chain_index = i
        chain_count = chain_cards.count(card)
        card.effect_description = card.get_effect_description(desc, True)
        chain_cards.append(card)
    cancel_message = _("Press escape to cancel chaining")
    if not forced:
        utils.output(_("Chaining, {message}").format(message=cancel_message))
    else:
        utils.output(_("Chaining"))
    logger.debug(f"Amount of chaining cards: {len(chain_cards)}")
    location_info_tabable = []
    for card in chain_cards:
        location_info_tabable.append(LocationConversion.from_card_location(client, card).to_zone_key())
    client.get_duel_field().tab_order.set_tabable_items(location_info_tabable)
    client.player.chaining_cards = chain_cards
    utils.get_ui_stack().play_duel_sound_effect("chain")
    client.get_duel_field().preemtive_key_handler = lambda client, event: chains_preemtive_key_handler(client, event, forced, chain_cards)

def chains_preemtive_key_handler(client, event, forced, chain_cards):
    logger.debug("handled by select chain keyboard handler")
    key = event.GetKeyCode()
    # if escape is pressed, cancel the chaining
    if key == wx.WXK_ESCAPE and not forced:
        logger.debug("Chaining canceled")
        client.get_duel_field().tab_order.set_tabable_items([])
        client.send(structs.ClientIdType.RESPONSE, struct.pack('i', -1))
        client.get_duel_field().preemtive_key_handler = None
        return True
    # if return (enter) is pressed, send the chaining id for that card.
    if key == wx.WXK_RETURN:
        zone = client.get_duel_field().get_zone_from_current_position()
        logger.debug(f"Resolving chain for zone: {zone}")
        return client.get_duel_field().resolve_chain(zone)
