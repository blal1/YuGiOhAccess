"""An action menu must not outlive the prompt it was built from.

The menu lists what the duel said was possible at the moment it opened. The next
prompt replaces that list wholesale. Acting on the old menu afterwards either
took the whole application down, or -- worse -- sent an index that now pointed
at a different action entirely.
"""

import struct
from types import SimpleNamespace

import pytest

from game.card.card import Card
from game.player import Player
from ui import action_menu, playable_cards


def _card(code=0, controller=0, location=2, sequence=0):
    card = Card(code)
    card.set_location_and_position_info(controller, location, sequence, 1)
    return card


def _player():
    """A Player without the music setup, which needs an installed data dir."""
    player = Player.__new__(Player)
    player.state_generation = 0
    player.clear_all()
    return player


def _client(mocker, activatable=None):
    player = _player()
    player.activatable = activatable if activatable is not None else []
    client = SimpleNamespace(player=player, send=mocker.MagicMock(), what_player_am_i=0)
    return client


@pytest.fixture(autouse=True)
def ui_stack(mocker):
    stack = mocker.MagicMock()
    mocker.patch("ui.action_menu.utils.get_ui_stack", return_value=stack)
    return stack


# ------------------------------------------------------- the state changed --

def test_player_state_has_a_generation_that_moves_on_each_prompt():
    player = _player()
    first = player.state_generation

    player.clear_all()

    assert player.state_generation != first


def test_acting_on_a_stale_menu_sends_nothing(mocker):
    card = _card()
    client = _client(mocker, activatable=[card])
    generation = client.player.state_generation
    # A new prompt arrives and replaces everything the menu was built from.
    client.player.clear_all()
    client.player.activatable = [_card(sequence=3), card]

    action_menu.send_activate(client, card, generation=generation)

    client.send.assert_not_called()


def test_the_player_is_told_why_nothing_happened(mocker):
    output = mocker.patch("ui.action_menu.utils.output")
    card = _card()
    client = _client(mocker, activatable=[card])
    generation = client.player.state_generation
    client.player.clear_all()

    action_menu.send_activate(client, card, generation=generation)

    assert output.called


def test_a_fresh_menu_still_acts(mocker):
    card = _card()
    client = _client(mocker, activatable=[card])

    action_menu.send_activate(client, card, generation=client.player.state_generation)

    client.send.assert_called_once()
    payload = client.send.call_args.args[1]
    assert struct.unpack("<I", payload)[0] == (0 << 16) + 5


def test_a_menu_with_no_generation_still_works(mocker):
    """Callers that never captured a generation keep their old behaviour."""
    card = _card()
    client = _client(mocker, activatable=[card])

    action_menu.send_activate(client, card)

    client.send.assert_called_once()


# ------------------------------------- the card is gone from the list anyway --

def test_an_action_that_vanished_does_not_crash(mocker):
    output = mocker.patch("ui.action_menu.utils.output")
    card = _card()
    client = _client(mocker, activatable=[])

    action_menu.send_activate(client, card)

    client.send.assert_not_called()
    assert output.called


@pytest.mark.parametrize(
    "sender,field",
    [
        (action_menu.send_attack, "attackable"),
        (action_menu.send_special_summon, "special_summonable"),
        (action_menu.send_summon, "summonable"),
        (action_menu.send_monster_set, "monster_settable"),
        (action_menu.send_spell_set, "spell_settable"),
        (action_menu.send_reposition, "repositionable"),
    ],
)
def test_every_action_refuses_gracefully_when_it_is_gone(mocker, sender, field):
    mocker.patch("ui.action_menu.utils.output")
    card = _card()
    client = _client(mocker)
    setattr(client.player, field, [])

    sender(client, card)

    client.send.assert_not_called()


def test_the_index_helper_still_reports_a_miss():
    with pytest.raises(ValueError):
        playable_cards.first_matching_index([], _card())
