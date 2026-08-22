import io
import logging

from core import utils
from core.i18n import _

logger = logging.getLogger(__name__)


@utils.duel_message_handler(95)
def msg_damage(client, data, data_length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    amount = client.read_u32(data)
    logger.debug(f"Damage: player={player}, amount={amount}")
    if player == client.what_player_am_i:
        utils.output(_("You took {amount} damage.").format(amount=amount))
        utils.get_ui_stack().play_duel_sound_effect("damage")
    else:
        utils.output(_("Your opponent took {amount} damage.").format(amount=amount))
