import io

from game.card import card_constants

from core import utils
from core.i18n import _
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_BATTLE)
def msg_battle(client, data, data_length):
    data = io.BytesIO(data[1:])
    attacker_controller, attacker_location, attacker_sequence, attacker_position = client.read_location(data)

    aa = client.read_u32(data)
    ad = client.read_u32(data)
    bd0 = client.read_u8(data)
    target_controller, target_location, target_sequence, target_position = client.read_location(data)
    da = client.read_u32(data)
    dd = client.read_u32(data)
    bd1 = client.read_u8(data)
    damage_step_battle(client, attacker_controller, attacker_location, attacker_sequence, attacker_position, aa, ad, bd0, target_controller, target_location, target_sequence, target_position, da, dd, bd1)


def _is_empty_location(controller, location, sequence, position):
    """Whether a location reference names no card at all.

    The core writes an all zero reference for a direct attack. Testing the
    fields one at a time with ``and`` treated any single zero as "no target",
    so a monster belonging to player 0, or one sitting in the first zone, was
    reported as an attack into thin air.
    """
    return not (controller or location or sequence or position)


def _battle_points(card, attack, defense):
    """A link monster has no defense to read out; everything else does."""
    if card is not None and getattr(card, "type", 0) & card_constants.TYPE.LINK:
        return "%d" % attack
    return "%d/%d" % (attack, defense)


def damage_step_battle(client, attacker_controller, attacker_location, attacker_sequence, attacker_position, aa, ad, bd0, target_controller, target_location, target_sequence, target_position, da, dd, bd1):
    attacking_card = client.get_card(attacker_controller, attacker_location, attacker_sequence)
    if _is_empty_location(target_controller, target_location, target_sequence, target_position):
        target = None
    else:
        target = client.get_card(target_controller, target_location, target_sequence)
    # get_card returns None for a zone the client has not been told about yet.
    # The numbers are still worth announcing, so only the name falls back.
    attacker_name = attacking_card.get_name() if attacking_card is not None else _("An unknown card")
    attacker_points = _battle_points(attacking_card, aa, ad)

    if target is not None:
        defender_points = _battle_points(target, da, dd)
        utils.output(_("%s (%s) attacks %s (%s)") % (attacker_name, attacker_points, target.get_name(), defender_points))
    else:
        utils.output(_("%s (%s) attacks") % (attacker_name, attacker_points))
