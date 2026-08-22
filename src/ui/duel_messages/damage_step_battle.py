import io

from game.card import card_constants

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(111)
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


def damage_step_battle(client, attacker_controller, attacker_location, attacker_sequence, attacker_position, aa, ad, bd0, target_controller, target_location, target_sequence, target_position, da, dd, bd1):
    attacking_card = client.get_card(attacker_controller, attacker_location, attacker_sequence)
    if target_controller != 0 and target_location != 0 and target_sequence != 0 and target_position != 0:
        target = client.get_card(target_controller, target_location, target_sequence)
    else:
        target = None
    if attacking_card.type & card_constants.TYPE.LINK:
        attacker_points = "%d"%aa
    else:
        attacker_points = "%d/%d"%(aa, ad)

    if target:
        if target.type & card_constants.TYPE.LINK:
            defender_points = "%d"%da
        else:
            defender_points = "%d/%d"%(da, dd)

    if target:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s (%s) attacks %s (%s)") % (attacking_card.get_name(), attacker_points, target.get_name(), defender_points)))
    else:
        utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("%s (%s) attacks") % (attacking_card.get_name(), attacker_points)))
