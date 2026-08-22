"""Tests for side decking UI logic."""
import struct
from unittest.mock import MagicMock, patch


def test_do_move_to_side(mocker):
    """Moving card from main to side updates lists."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mocker.patch("ui.side_deck_ui.Card")
    mocker.patch("ui.side_deck_ui._show_side_menu")

    from ui.side_deck_ui import _do_move_to_side
    client = MagicMock()
    main_cards = [1001, 1002, 1003]
    side_cards = [2001]
    moved_to_side = []
    moved_to_main = []

    _do_move_to_side(client, main_cards, side_cards, moved_to_side, moved_to_main, 1002)

    assert 1002 not in main_cards
    assert 1002 in side_cards
    assert 1002 in moved_to_side


def test_do_move_to_main(mocker):
    """Moving card from side to main updates lists."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mocker.patch("ui.side_deck_ui.Card")
    mocker.patch("ui.side_deck_ui._show_side_menu")

    from ui.side_deck_ui import _do_move_to_main
    client = MagicMock()
    main_cards = [1001]
    side_cards = [2001, 2002]
    moved_to_side = []
    moved_to_main = []

    _do_move_to_main(client, main_cards, side_cards, moved_to_side, moved_to_main, 2001)

    assert 2001 in main_cards
    assert 2001 not in side_cards
    assert 2001 in moved_to_main


def test_submit_side_deck_sends_packet(mocker):
    """Submit side deck sends UPDATE_DECK with correct data."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")

    from game.edo import structs
    mock_deck = MagicMock()
    mocker.patch("game.edo.structs.Deck", return_value=mock_deck)

    from ui.side_deck_ui import _submit_side_deck
    client = MagicMock()
    client.memory = MagicMock()
    main_cards = [1001, 1002]
    side_cards = [2001]

    _submit_side_deck(client, main_cards, side_cards)

    mock_deck.set_main_deck.assert_called_once_with(main_cards)
    mock_deck.set_side_deck.assert_called_once_with(side_cards)
    client.send.assert_called_once_with(structs.ClientIdType.UPDATE_DECK, mock_deck)


def test_show_side_deck_no_deck(mocker):
    """show_side_deck_ui outputs error when no deck loaded."""
    mocker.patch("core.utils.output")
    from ui.side_deck_ui import show_side_deck_ui
    client = MagicMock()
    client.memory = MagicMock(spec=[])  # no 'deck' attribute
    show_side_deck_ui(client)
    from core.utils import output
    output.assert_called()
