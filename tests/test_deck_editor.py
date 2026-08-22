"""Tests for deck editor logic."""
from unittest.mock import MagicMock, patch


def test_is_extra_deck_card_fusion(mocker):
    """Fusion monster detected as extra deck card."""
    from game.card import card_constants
    mock_card = MagicMock()
    mock_card.type = card_constants.TYPE.FUSION
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)

    from ui.deck_editor_ui import _is_extra_deck_card
    assert _is_extra_deck_card(12345) is True


def test_is_extra_deck_card_normal_monster(mocker):
    """Normal monster is not extra deck card."""
    mock_card = MagicMock()
    mock_card.type = 0x11  # Normal monster
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)

    from ui.deck_editor_ui import _is_extra_deck_card
    assert _is_extra_deck_card(12345) is False


def test_is_extra_deck_card_exception(mocker):
    """Returns False on exception (unknown card)."""
    mocker.patch("ui.deck_editor_ui.Card", side_effect=Exception("not found"))

    from ui.deck_editor_ui import _is_extra_deck_card
    assert _is_extra_deck_card(99999) is False


def test_add_card_main_deck_full(mocker):
    """Cannot add to main deck when at 60 cards."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mock_card = MagicMock()
    mock_card.type = 0x11  # Not extra deck
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)
    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=False)
    mocker.patch("ui.deck_editor_ui.edit_deck")

    from ui.deck_editor_ui import add_card_to_deck, MAX_MAIN_DECK
    deck_data = {"main": [i for i in range(MAX_MAIN_DECK)], "side": []}

    add_card_to_deck("test", deck_data, 9999, None)

    from core.utils import output
    assert any("full" in str(c) for c in output.call_args_list)
    assert len(deck_data["main"]) == MAX_MAIN_DECK


def test_add_card_3_copy_limit(mocker):
    """Cannot add more than 3 copies of same card."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mock_card = MagicMock()
    mock_card.type = 0x11
    mock_card.get_name.return_value = "Blue-Eyes"
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)
    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=False)
    mocker.patch("ui.deck_editor_ui.edit_deck")

    from ui.deck_editor_ui import add_card_to_deck
    deck_data = {"main": [100, 100, 100], "side": []}

    add_card_to_deck("test", deck_data, 100, None)

    from core.utils import output
    assert any("3 copies" in str(c) for c in output.call_args_list)


def test_add_card_to_side(mocker):
    """Can add directly to side deck with copy limits."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mocker.patch("ui.deck_editor_ui.edit_deck")
    mock_card = MagicMock()
    mock_card.get_name.return_value = "Side Card"
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)

    from ui.deck_editor_ui import add_card_to_side
    deck_data = {"main": [], "side": []}

    add_card_to_side("test", deck_data, 123, None)

    assert deck_data["side"] == [123]


def test_validate_deck_for_save(mocker):
    """Save validation catches invalid sizes and copy limits."""
    mock_card = MagicMock()
    mock_card.get_name.return_value = "Too Many"
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)
    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=False)

    from ui.deck_editor_ui import _validate_deck_for_save

    assert "at least" in _validate_deck_for_save({"main": [1], "side": []})
    assert _validate_deck_for_save({"main": list(range(40)), "side": []}) is None
    assert "3 copies" in _validate_deck_for_save({"main": [1] * 4 + list(range(2, 40)), "side": []})


def test_do_remove_card(mocker):
    """Removing a card decreases count."""
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    mock_card = MagicMock()
    mock_card.get_name.return_value = "Test Card"
    mocker.patch("ui.deck_editor_ui.Card", return_value=mock_card)
    mocker.patch("ui.deck_editor_ui.edit_deck")

    from ui.deck_editor_ui import _do_remove
    deck_data = {"main": [100, 200, 100], "side": []}

    _do_remove("test", deck_data, "main", 100, None)

    assert deck_data["main"].count(100) == 1
    assert 200 in deck_data["main"]
