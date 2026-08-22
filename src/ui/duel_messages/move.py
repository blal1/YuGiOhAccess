import io
import logging
from enum import IntFlag

from core import dotdict, exceptions
from core import utils
from core.i18n import _

from game.card.card import Card
from game.card.location_conversion import LocationConversion
from game.card import card_constants

logger = logging.getLogger(__name__)

@utils.duel_message_handler(50)
def msg_move(client, data, data_length):
    data = io.BytesIO(data[1:])
    code = client.read_u32(data)
    old_controller, old_location, old_sequence, old_position = client.read_location(data)
    new_controller, new_location, new_sequence, new_position = client.read_location(data)
    reason = card_constants.REASON(client.read_u32(data))
    move(client, code, old_controller, old_location, old_sequence, old_position, new_controller, new_location, new_sequence, new_position, reason)

def move(client, code, old_controller, old_location, old_sequence, old_position, new_controller, new_location, new_sequence, new_position, reason):
    logger.debug(f"Move: {code}, {old_controller}, {old_location}, {old_sequence}, {old_position}, {new_controller}, {new_location}, {new_sequence}, {new_position}, {reason}")
    try:
        card = Card(code)
    except exceptions.CardNotFoundException:
        return
    card.set_location_and_position_info(old_controller, old_location, old_sequence, old_position)
    cnew = Card(code)
    cnew.set_location_and_position_info(new_controller, new_location, new_sequence, new_position)
    logger.debug(f"{card.name} moved from {old_location} to {new_location} because of {reason}")
    # remove the card from the old location
    client.get_duel_field().remove_card(card)
    if new_location == card_constants.LOCATION.GRAVE:
        if new_controller == client.what_player_am_i:
            client.get_duel_field().append_card_to_player_graveyard(cnew)
        else:
            fake_query = dotdict.DotDict()
            fake_query.controller = new_controller
            fake_query.location = new_location
            fake_query.sequence = new_sequence
            fake_query.position = new_position
            client.get_duel_field().append_card_to_opponent_graveyard(cnew, fake_query)
    elif new_location == card_constants.LOCATION.REMOVED:
        if new_controller == client.what_player_am_i:
            client.get_duel_field().append_card_to_player_banished(cnew)
        else:
            fake_query = dotdict.DotDict()
            fake_query.controller = new_controller
            fake_query.location = new_location
            fake_query.sequence = new_sequence
            fake_query.position = new_position
            client.get_duel_field().append_card_to_opponent_banished(cnew, fake_query)
    message = get_message_to_announce(client, card, cnew, reason)
    if message:
        utils.output(_("{message}").format(message=message))
    else:
        logger.debug(f"No announce message for: {card.name} moved from {old_location} to {new_location} because of {reason}")


class Message(IntFlag):
    ME = 0x1
    OPPONENT = 0x2

def get_message_to_announce(client, card, cnew, reason):
    old_location_information = LocationConversion.from_card_location(client, card)  # noqa: F841
    new_card_information = LocationConversion.from_card_location(client, cnew)
    name = card.get_name()
    loc = new_card_information.to_human_readable()
    is_mine = card.controller == client.what_player_am_i

    if reason & card_constants.REASON.DESTROY and card.location != cnew.location:
        utils.get_ui_stack().play_duel_sound_effect("destroy")
        if is_mine:
            return _("Your card {name} destroyed.").format(name=name)
        return _("Your opponent's card {name} destroyed.").format(name=name)
    elif card.location == cnew.location and card.location & card_constants.LOCATION.ONFIELD:
        if card.controller != cnew.controller:
            utils.get_ui_stack().play_duel_sound_effect("swapcontrol")
            if is_mine:
                return _("Your card {name} switched control to your opponent, and is now located at {location}.").format(name=name, location=loc)
            return _("Your opponent's card {name} switched control to you, and is now located at {location}.").format(name=name, location=loc)
        else:
            if is_mine:
                return _("Your card {name} changed column to {location}.").format(name=name, location=loc)
            return _("Your opponent's card {name} changed column to {location}.").format(name=name, location=loc)
    elif reason & card_constants.REASON.DISCARD and card.location != cnew.location:
        utils.get_ui_stack().play_duel_sound_effect("discard")
        if is_mine:
            return _("You discarded {name}.").format(name=name)
        return _("Your opponent discarded {name}.").format(name=name)
    elif card.location == card_constants.LOCATION.REMOVED and cnew.location & card_constants.LOCATION.ONFIELD:
        if is_mine:
            return _("Your banished card {name} returns to the field at {location}.").format(name=name, location=loc)
        return _("Your opponent's banished card {name} returns to the field at {location}.").format(name=name, location=loc)
    elif card.location == card_constants.LOCATION.GRAVE and cnew.location & card_constants.LOCATION.ONFIELD:
        if is_mine:
            return _("Your card {name} returns from the graveyard to the field at {location}.").format(name=name, location=loc)
        return _("Your opponent's card {name} returns from the graveyard to the field at {location}.").format(name=name, location=loc)
    elif cnew.location == card_constants.LOCATION.HAND and card.location != cnew.location:
        utils.get_ui_stack().play_duel_sound_effect("return")
        if is_mine:
            return _("{name} returned to your hand.").format(name=name)
        return _("{name} returned to your opponent's hand.").format(name=name)
    elif reason & (card_constants.REASON.RELEASE | card_constants.REASON.SUMMON) and card.location != cnew.location:
        utils.get_ui_stack().play_duel_sound_effect("tribute")
        if is_mine:
            return _("You tributed {name}.").format(name=name)
        return _("Your opponent tributed {name}.").format(name=name)
    elif card.location == card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE and cnew.location & card_constants.LOCATION.GRAVE:
        utils.get_ui_stack().play_duel_sound_effect("detach")
        if is_mine:
            return _("You used overlay unit {name}.").format(name=name)
        return _("Your opponent used overlay unit {name}.").format(name=name)
    elif card.location != cnew.location and cnew.location == card_constants.LOCATION.GRAVE:
        utils.get_ui_stack().play_duel_sound_effect("sendtograve")
        if is_mine:
            return _("Your {name} was sent to the graveyard.").format(name=name)
        return _("Your opponent's {name} was sent to the graveyard.").format(name=name)
    elif card.location != cnew.location and cnew.location == card_constants.LOCATION.REMOVED:
        if is_mine:
            return _("Your {name} was banished.").format(name=name)
        return _("Your opponent's {name} was banished.").format(name=name)
    elif card.location != cnew.location and cnew.location == card_constants.LOCATION.DECK:
        utils.get_ui_stack().play_duel_sound_effect("sendtodeck")
        if is_mine:
            return _("Your {name} returned to your deck.").format(name=name)
        return _("Your opponent's {name} returned to their deck.").format(name=name)
    elif card.location != cnew.location and cnew.location == card_constants.LOCATION.EXTRA:
        utils.get_ui_stack().play_duel_sound_effect("sendtoextradeck")
        if is_mine:
            return _("Your {name} returned to your extra deck.").format(name=name)
        return _("Your opponent's {name} returned to their extra deck.").format(name=name)
    elif card.location == card_constants.LOCATION.DECK and cnew.location == card_constants.LOCATION.SPELL_AND_TRAP_ZONE and cnew.position != card_constants.POSITION.FACE_DOWN:
        if is_mine:
            return _("You activate {name} from your deck.").format(name=name)
        return _("Your opponent activates {name} from their deck.").format(name=name)
    elif cnew.location == (card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE):
        attached_to = client.get_card(cnew.controller, cnew.location ^ card_constants.LOCATION.OVERLAY, cnew.sequence)
        attached_name = attached_to.get_name() if attached_to else _("unknown card")
        if is_mine:
            return _("Your card {name} was attached to {target} as XYZ material.").format(name=name, target=attached_name)
        return _("Your opponent's card {name} was attached to {target} as XYZ material.").format(name=name, target=attached_name)
