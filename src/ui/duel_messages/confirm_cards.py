import io

from game.card.card import Card
from game.card import card_constants

from core import utils
from core.i18n import _
from core import variables

@utils.duel_message_handler(31)
def msg_confirm_cards(client, data, data_length):
	data = io.BytesIO(data[1:])
	player = client.read_u8(data)
	size = client.read_u32(data)
	cards = []
	for i in range(size):
		code = client.read_u32(data)
		card = Card(code)
		controller = client.read_u8(data)
		location = card_constants.LOCATION(client.read_u8(data))
		sequence = client.read_u32(data)
		card.controller = controller
		card.location = location
		card.sequence = sequence
		cards.append(card)
	confirm_cards(client, player, size, cards)
	return data.read()

def confirm_cards(client, to_player, size, cards):
	_player = ""
	_opponent = ""
	if to_player != client.what_player_am_i:
		_player = "You"
		_opponent = "Your opponent"
	else:
		_player = "Your opponent"
		_opponent = "You"
	utils.output(_("{message}").format(message=variables.LANGUAGE_HANDLER._("{player} shows {opponent} {count} cards.")
			.format(player=_player, opponent=_opponent, count=len(cards))))
	for i, c in enumerate(cards):
		utils.output(_("{index}: {name}").format(index=i + 1, name=c.get_name()))
