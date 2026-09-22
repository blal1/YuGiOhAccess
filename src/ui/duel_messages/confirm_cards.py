import io

from game.card.card import Card
from game.card import card_constants

from core import utils
from core.i18n import _, ngettext
from game.edo import message_constants

@utils.duel_message_handler(message_constants.MSG_CONFIRM_CARDS)
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
	# One whole sentence per case. Substituting "You" and "Your opponent" into
	# a shared sentence left both of them in English, and no language that
	# inflects its verbs can be translated that way anyway.
	count = len(cards)
	if to_player != client.what_player_am_i:
		message = ngettext(
			"You show your opponent {count} card.",
			"You show your opponent {count} cards.",
			count,
		)
	else:
		message = ngettext(
			"Your opponent shows you {count} card.",
			"Your opponent shows you {count} cards.",
			count,
		)
	utils.output(message.format(count=count))
	for i, c in enumerate(cards):
		utils.output(_("{index}: {name}").format(index=i + 1, name=c.get_name()))
