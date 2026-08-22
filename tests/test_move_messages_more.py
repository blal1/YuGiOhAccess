from unittest.mock import MagicMock


class MoveCard:
    def __init__(self, code=1):
        from game.card import card_constants

        self.code = code
        self.name = f"Card {code}"
        self.controller = 0
        self.location = card_constants.LOCATION.DECK
        self.sequence = 0
        self.position = card_constants.POSITION.FACE_UP_ATTACK

    def set_location_and_position_info(self, controller, location, sequence, position):
        self.controller = controller
        self.location = location
        self.sequence = sequence
        self.position = position

    def get_name(self):
        return self.name


def _client():
    client = MagicMock()
    client.what_player_am_i = 0
    client.get_duel_field.return_value.remove_card = MagicMock()
    client.get_duel_field.return_value.append_card_to_player_graveyard = MagicMock()
    client.get_duel_field.return_value.append_card_to_opponent_graveyard = MagicMock()
    client.get_duel_field.return_value.append_card_to_player_banished = MagicMock()
    client.get_duel_field.return_value.append_card_to_opponent_banished = MagicMock()
    return client


def _card(location, controller=0, sequence=0):
    card = MoveCard(100 + sequence)
    card.location = location
    card.controller = controller
    card.sequence = sequence
    return card


def _loc(sequence=0):
    loc = MagicMock()
    loc.sequence = sequence
    loc.to_human_readable.return_value = f"zone {sequence}"
    return loc


def test_get_message_to_announce_all_major_reasons(mocker):
    from game.card import card_constants
    from ui.duel_messages import move

    client = _client()
    mocker.patch("ui.duel_messages.move.LocationConversion.from_card_location", return_value=_loc(2))
    mocker.patch("ui.duel_messages.move.utils.get_ui_stack", return_value=MagicMock())

    cases = [
        (_card(card_constants.LOCATION.MONSTER_ZONE), _card(card_constants.LOCATION.GRAVE), card_constants.REASON.DESTROY, "destroyed"),
        (_card(card_constants.LOCATION.MONSTER_ZONE, 0), _card(card_constants.LOCATION.MONSTER_ZONE, 1), 0, "switched control"),
        (_card(card_constants.LOCATION.MONSTER_ZONE), _card(card_constants.LOCATION.MONSTER_ZONE), 0, "changed column"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.GRAVE), card_constants.REASON.DISCARD, "discarded"),
        (_card(card_constants.LOCATION.REMOVED), _card(card_constants.LOCATION.MONSTER_ZONE), 0, "banished card"),
        (_card(card_constants.LOCATION.GRAVE), _card(card_constants.LOCATION.MONSTER_ZONE), 0, "graveyard"),
        (_card(card_constants.LOCATION.DECK), _card(card_constants.LOCATION.HAND), 0, "hand"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.GRAVE), card_constants.REASON.RELEASE, "tributed"),
        (_card(card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE), _card(card_constants.LOCATION.GRAVE), 0, "overlay"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.GRAVE), 0, "graveyard"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.REMOVED), 0, "banished"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.DECK), 0, "deck"),
        (_card(card_constants.LOCATION.HAND), _card(card_constants.LOCATION.EXTRA), 0, "extra deck"),
        (_card(card_constants.LOCATION.DECK), _card(card_constants.LOCATION.SPELL_AND_TRAP_ZONE), 0, "activate"),
    ]

    for old_card, new_card, reason, expected in cases:
        message = move.get_message_to_announce(client, old_card, new_card, reason)
        assert expected.lower() in message.lower()

    overlay = _card(card_constants.LOCATION.HAND)
    overlay_target = _card(card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE)
    client.get_card.return_value = MoveCard(999)
    assert "XYZ material" in move.get_message_to_announce(client, overlay, overlay_target, 0)


def test_get_message_to_announce_opponent_variants(mocker):
    from game.card import card_constants
    from ui.duel_messages import move

    client = _client()
    mocker.patch("ui.duel_messages.move.LocationConversion.from_card_location", return_value=_loc(3))
    mocker.patch("ui.duel_messages.move.utils.get_ui_stack", return_value=MagicMock())

    old_card = _card(card_constants.LOCATION.HAND, controller=1)
    new_card = _card(card_constants.LOCATION.GRAVE, controller=1)
    assert "opponent" in move.get_message_to_announce(client, old_card, new_card, card_constants.REASON.DISCARD).lower()


def test_move_updates_field_and_outputs_message(mocker):
    from game.card import card_constants
    from ui.duel_messages import move

    client = _client()
    card_cls = mocker.patch("ui.duel_messages.move.Card", side_effect=lambda code: MoveCard(code))
    mocker.patch("ui.duel_messages.move.utils.output")
    mocker.patch("ui.duel_messages.move.get_message_to_announce", return_value="moved")

    move.move(
        client,
        123,
        0,
        card_constants.LOCATION.HAND,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        0,
        card_constants.LOCATION.GRAVE,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        0,
    )

    assert card_cls.call_count == 2
    client.get_duel_field.return_value.remove_card.assert_called()
    client.get_duel_field.return_value.append_card_to_player_graveyard.assert_called()
    move.utils.output.assert_called_once_with("moved")


def test_move_handles_unknown_card_and_append_destinations(mocker):
    from core import exceptions
    from game.card import card_constants
    from ui.duel_messages import move

    client = _client()
    mocker.patch("ui.duel_messages.move.Card", side_effect=exceptions.CardNotFoundException("missing"))
    assert move.move(client, 999, 0, 1, 0, 1, 0, 2, 0, 1, 0) is None

    mocker.patch("ui.duel_messages.move.Card", side_effect=lambda code: MoveCard(code))
    mocker.patch("ui.duel_messages.move.utils.output")
    mocker.patch("ui.duel_messages.move.get_message_to_announce", return_value=None)

    for controller, location, expected in [
        (1, card_constants.LOCATION.GRAVE, "append_card_to_opponent_graveyard"),
        (0, card_constants.LOCATION.REMOVED, "append_card_to_player_banished"),
        (1, card_constants.LOCATION.REMOVED, "append_card_to_opponent_banished"),
    ]:
        move.move(client, 123, 0, card_constants.LOCATION.HAND, 0, 1, controller, location, 0, 1, 0)
        assert getattr(client.get_duel_field.return_value, expected).called
