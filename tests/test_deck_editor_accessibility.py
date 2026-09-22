"""Tests for the deck editor accessibility work and the shared card reader."""

from unittest.mock import MagicMock

import pytest

from tests.test_ui_flows_more import FakeMenu


def _patch_editor(mocker, tmp_path):
    from ui import deck_editor_ui

    mocker.patch("ui.deck_editor_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.deck_editor_ui.CardChoiceMenu", FakeMenu)
    mocker.patch("ui.deck_editor_ui.utils.get_ui_stack", return_value=MagicMock())
    mocker.patch("ui.deck_editor_ui.utils.output")
    mocker.patch("ui.deck_editor_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    card = MagicMock()
    card.get_name.return_value = "Blue-Eyes"
    mocker.patch("ui.deck_editor_ui.Card", return_value=card)
    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=False)
    deck_editor_ui.variables.DECK_DIR = tmp_path
    deck_editor_ui.variables.LANGUAGE_HANDLER = MagicMock()
    return deck_editor_ui


def _said(module):
    return [str(call) for call in module.utils.output.call_args_list]


# --------------------------------------------------------- card text splitting

def test_long_effect_text_is_split_into_sentences():
    from ui.card_details_ui import split_card_detail_lines

    text = (
        "Blue-Eyes White Dragon (Monster, Dragon)\n"
        "This legendary dragon is a powerful engine of destruction. "
        "Virtually invincible, very few have faced this awesome creature and lived to tell the tale."
    )
    lines = split_card_detail_lines(text)
    assert lines[0].startswith("Blue-Eyes White Dragon")
    # The effect used to arrive as a single unreadable line.
    assert len(lines) == 3
    assert lines[1].endswith("destruction.")
    assert lines[2].startswith("Virtually invincible")


def test_splitting_keeps_short_lines_intact_and_never_returns_nothing():
    from ui.card_details_ui import split_card_detail_lines

    assert split_card_detail_lines("Name\nStats\nEffect") == ["Name", "Stats", "Effect"]
    assert split_card_detail_lines("\n \n") == ["No details."]


def test_a_very_long_sentence_is_split_on_clauses():
    from ui.card_details_ui import split_card_detail_lines, LONG_SEGMENT

    first = "A" * (LONG_SEGMENT - 10)
    sentence = f"{first}; and then something else entirely happens afterwards"
    lines = split_card_detail_lines(sentence)
    assert len(lines) == 2
    assert lines[0].endswith(";")


# ------------------------------------------------------------ card choice menu

def _bare_choice_menu():
    """A CardChoiceMenu without the wx machinery, for the bookkeeping logic."""
    from ui.card_details_ui import CardChoiceMenu

    menu = CardChoiceMenu.__new__(CardChoiceMenu)
    menu.codes_by_row = {}
    menu.rows = 0
    menu.current_row = 0
    menu.appended = []

    def append_item(label, function=None):
        menu.appended.append(label)
        menu.rows += 1
        return label

    def append_cancel_item(label, function=None):
        menu.cancel_action = function
        return append_item(label, function)

    menu.append_item = append_item
    menu.append_cancel_item = append_cancel_item
    return menu


def test_card_choice_menu_tracks_the_code_under_the_cursor():
    menu = _bare_choice_menu()
    menu.append_card(10, "Alpha")
    menu.append_card(20, "Beta")

    assert menu.codes_by_row == {0: 10, 1: 20}
    assert menu.appended == ["Alpha", "Beta"]

    menu.current_row = 1
    assert menu.current_code() == 20
    # A heading row carries no card, and reading it must not blow up.
    menu.current_row = 7
    assert menu.current_code() is None


def test_space_on_a_card_row_opens_the_reader(mocker):
    show = mocker.patch("ui.card_details_ui.show_card_details", return_value="reader")
    output = mocker.patch("ui.card_details_ui.utils.output")

    menu = _bare_choice_menu()
    menu.append_card(10, "Alpha")

    assert menu.read_current_card() == "reader"
    show.assert_called_once_with(10)

    menu.current_row = 3
    assert menu.read_current_card() is None
    assert any("No card on this line" in str(call) for call in output.call_args_list)


# ------------------------------------------------------- banlist aware limits

def test_copy_limit_follows_the_selected_banlist(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    banlist = MagicMock()
    banlist.get_limit.return_value = 1
    mocker.patch("ui.deck_editor_ui.banlists.BanlistManager").return_value.get_banlist_by_name.return_value = banlist
    mocker.patch("ui.deck_editor_ui.edit_deck")

    deck_data = {"main": [100], "side": [], "banlist": "TCG"}
    assert deck_editor_ui._max_copies(deck_data, 100) == 1

    deck_editor_ui.add_card_to_deck("test", deck_data, 100, None)

    assert deck_data["main"] == [100]
    assert any("limited to one copy" in call for call in _said(deck_editor_ui))


def test_without_a_banlist_three_copies_are_allowed(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.edit_deck")
    deck_data = {"main": [100, 100], "side": []}

    assert deck_editor_ui._max_copies(deck_data, 100) == deck_editor_ui.DEFAULT_MAX_COPIES
    deck_editor_ui.add_card_to_deck("test", deck_data, 100, None)
    assert deck_data["main"].count(100) == 3

    deck_editor_ui.add_card_to_deck("test", deck_data, 100, None)
    assert deck_data["main"].count(100) == 3
    assert any("3 copies" in call for call in _said(deck_editor_ui))


def test_a_forbidden_card_is_reported_as_forbidden(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    banlist = MagicMock()
    banlist.get_limit.return_value = 0
    mocker.patch("ui.deck_editor_ui.banlists.BanlistManager").return_value.get_banlist_by_name.return_value = banlist
    mocker.patch("ui.deck_editor_ui.edit_deck")

    deck_data = {"main": [], "side": [], "banlist": "TCG"}
    deck_editor_ui.add_card_to_deck("test", deck_data, 100, None)

    assert deck_data["main"] == []
    assert any("forbidden" in call for call in _said(deck_editor_ui))


def test_an_unreadable_banlist_falls_back_to_three(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.banlists.BanlistManager", side_effect=RuntimeError("no banlists"))
    deck_data = {"main": [], "side": [], "banlist": "Missing"}
    assert deck_editor_ui._max_copies(deck_data, 100) == deck_editor_ui.DEFAULT_MAX_COPIES


# ----------------------------------------------------- staying where you were

def test_adding_a_copy_keeps_you_in_the_results(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    edit_deck = mocker.patch("ui.deck_editor_ui.edit_deck")
    back_to_results = MagicMock()

    deck_data = {"main": [], "side": []}
    deck_editor_ui.add_card_to_deck("test", deck_data, 100, None, after=back_to_results)

    back_to_results.assert_called_once()
    edit_deck.assert_not_called()
    assert any("1 in deck" in call for call in _said(deck_editor_ui))


def test_removing_a_copy_keeps_you_in_the_remove_list(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    edit_deck = mocker.patch("ui.deck_editor_ui.edit_deck")
    stay = MagicMock()

    deck_data = {"main": [100, 100], "side": []}
    deck_editor_ui._do_remove("test", deck_data, "main", 100, None, after=stay)

    assert deck_data["main"] == [100]
    stay.assert_called_once()
    edit_deck.assert_not_called()
    assert any("1 left" in call for call in _said(deck_editor_ui))


def test_removing_the_last_card_returns_to_the_deck_menu(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    edit_deck = mocker.patch("ui.deck_editor_ui.edit_deck")
    stay = MagicMock()

    deck_data = {"main": [100], "side": []}
    deck_editor_ui._do_remove("test", deck_data, "main", 100, None, after=stay)

    assert deck_data["main"] == []
    stay.assert_not_called()
    edit_deck.assert_called_once()


def test_adding_several_copies_at_once(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.edit_deck")

    deck_data = {"main": [], "side": []}
    deck_editor_ui.add_copies_to_deck("test", deck_data, 100, 3, None)

    assert deck_data["main"] == [100, 100, 100]
    assert any("3 copies" in call for call in _said(deck_editor_ui))


def test_adding_several_copies_stops_at_the_limit(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.edit_deck")

    deck_data = {"main": [100, 100], "side": []}
    deck_editor_ui.add_copies_to_deck("test", deck_data, 100, 3, None)

    assert deck_data["main"].count(100) == 3
    assert any("Already have 3 copies" in call for call in _said(deck_editor_ui))


# ------------------------------------------------------------- shared search

def test_search_goes_through_the_card_search_engine(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    input_cls = mocker.patch("ui.deck_editor_ui.InputUI")
    input_cls.return_value.show.return_value = "blue"
    search = mocker.patch("ui.deck_editor_ui.card_search_ui.search_cards", return_value=[(10, "Blue-Eyes")])
    mocker.patch("ui.deck_editor_ui.card_search_ui.format_card_summary", return_value="monster, ATK 3000 DEF 2500")

    deck_data = {"main": [], "side": []}
    menu = deck_editor_ui.search_card_to_add.__wrapped__("Deck", deck_data, None)

    # The editor no longer runs its own LIKE query, so translations and filters
    # behave exactly as they do in Card Search.
    search.assert_called_once_with(name_query="blue")
    assert any("Blue-Eyes, monster, ATK 3000 DEF 2500" in item[0] for item in menu.items)
    assert menu.codes_by_row[0] == 10


def test_search_reports_how_many_copies_you_already_hold(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    input_cls = mocker.patch("ui.deck_editor_ui.InputUI")
    input_cls.return_value.show.return_value = "blue"
    mocker.patch("ui.deck_editor_ui.card_search_ui.search_cards", return_value=[(10, "Blue-Eyes")])
    mocker.patch("ui.deck_editor_ui.card_search_ui.format_card_summary", return_value="monster")

    deck_data = {"main": [10, 10], "side": []}
    menu = deck_editor_ui.search_card_to_add.__wrapped__("Deck", deck_data, None)

    assert any("2 already in deck" in item[0] for item in menu.items)


def test_search_announces_a_truncated_result_set(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    input_cls = mocker.patch("ui.deck_editor_ui.InputUI")
    input_cls.return_value.show.return_value = "a"
    limit = deck_editor_ui.card_search_ui.SEARCH_LIMIT
    mocker.patch("ui.deck_editor_ui.card_search_ui.search_cards", return_value=[(i, f"Card {i}") for i in range(limit)])
    mocker.patch("ui.deck_editor_ui.card_search_ui.format_card_summary", return_value="monster")

    deck_editor_ui.search_card_to_add.__wrapped__("Deck", {"main": [], "side": []}, None)

    assert any("showing the first" in call for call in _said(deck_editor_ui))


def test_a_bad_filter_is_reported_rather_than_raised(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    input_cls = mocker.patch("ui.deck_editor_ui.InputUI")
    input_cls.return_value.show.return_value = "blue"
    mocker.patch("ui.deck_editor_ui.card_search_ui.search_cards", side_effect=ValueError("Unknown card type"))
    edit_deck = mocker.patch("ui.deck_editor_ui.edit_deck")

    assert deck_editor_ui.search_card_to_add.__wrapped__("Deck", {"main": [], "side": []}, None) is None
    edit_deck.assert_called_once()
    assert any("Unknown card type" in call for call in _said(deck_editor_ui))


# ---------------------------------------------------------------- draft saves

def test_an_incomplete_deck_still_saves_as_a_draft(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.deck_editor_main_menu")
    deck = MagicMock()
    deck.to_json.return_value = '{"main": [1]}'
    mocker.patch("ui.deck_editor_ui.Deck", return_value=deck)

    deck_editor_ui.save_deck("Draft", {"main": [1], "side": []}, None)

    assert (tmp_path / "Draft.json").exists()
    assert any("saved as a draft" in call for call in _said(deck_editor_ui))


def test_a_legal_deck_saves_without_a_warning(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui.deck_editor_main_menu")
    mocker.patch("ui.deck_editor_ui._validate_deck_for_save", return_value=None)
    deck = MagicMock()
    deck.to_json.return_value = "{}"
    mocker.patch("ui.deck_editor_ui.Deck", return_value=deck)

    deck_editor_ui.save_deck("Good", {"main": list(range(40)), "side": []}, None)

    said = _said(deck_editor_ui)
    assert any("saved" in call for call in said)
    assert not any("draft" in call for call in said)


def test_the_deck_menu_reads_the_current_status(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)

    menu = deck_editor_ui.edit_deck.__wrapped__("Deck", {"main": [1], "side": []}, None)
    assert any("Status:" in item[0] and "at least" in item[0] for item in menu.items)

    mocker.patch("ui.deck_editor_ui._validate_deck_for_save", return_value=None)
    menu = deck_editor_ui.edit_deck.__wrapped__("Deck", {"main": list(range(40)), "side": []}, None)
    assert any("ready to play" in item[0] for item in menu.items)


def test_the_deck_menu_offers_the_banlist_in_use(mocker, tmp_path):
    deck_editor_ui = _patch_editor(mocker, tmp_path)

    menu = deck_editor_ui.edit_deck.__wrapped__("Deck", {"main": [], "side": []}, None)
    assert any("none, three copies allowed" in item[0] for item in menu.items)

    menu = deck_editor_ui.edit_deck.__wrapped__("Deck", {"main": [], "side": [], "banlist": "TCG"}, None)
    assert any("TCG" in item[0] for item in menu.items)


@pytest.mark.parametrize("section", ["main", "side"])
def test_view_deck_list_exposes_the_card_codes_for_reading(mocker, tmp_path, section):
    deck_editor_ui = _patch_editor(mocker, tmp_path)
    mocker.patch("ui.deck_editor_ui._group_cards_by_section", return_value=[("Monsters", {10: 2})])

    menu = deck_editor_ui.view_deck_list.__wrapped__("Deck", {"main": [10, 10], "side": [10, 10]}, section, None)

    # Space on any of these rows reads the card, which is what codes_by_row is for.
    assert 10 in menu.codes_by_row.values()
