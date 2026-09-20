from unittest.mock import MagicMock

import pytest
import wx

from tests.test_ui_flows_more import FakeMenu


def _patch_card_search(mocker):
    from ui import card_search_ui

    mocker.patch("ui.card_search_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.card_search_ui.utils.output")
    card_search_ui.variables.LANGUAGE_HANDLER = MagicMock()
    return card_search_ui


def _wx_frame():
    app = wx.GetApp() or wx.App(False)
    frame = wx.Frame(None)
    frame.push_ui = MagicMock()
    frame.pop_ui = MagicMock()
    frame.Close = MagicMock()
    frame.output = MagicMock()
    frame.sound_effects_audio_manager = MagicMock()
    return app, frame


class FakeKeyEvent:
    def __init__(self, key):
        self.key = key
        self.skipped = False

    def GetKeyCode(self):
        return self.key

    def Skip(self):
        self.skipped = True


def test_card_search_menu_and_name_search(mocker):
    card_search_ui = _patch_card_search(mocker)
    return_to = MagicMock()

    mocker.patch("ui.main_ui.main_menu_view", return_value="main")
    default_menu = card_search_ui.card_search_menu.__wrapped__()
    assert any(item[0] == "Back" for item in default_menu.items)

    menu = card_search_ui.card_search_menu.__wrapped__(return_to)
    assert any(item[0] == "Search by name" for item in menu.items)
    assert any(item[0] == "Advanced search" for item in menu.items)

    input_cls = mocker.patch("ui.card_search_ui.InputUI")
    input_cls.return_value.show.return_value = ""
    mocker.patch("ui.card_search_ui.card_search_menu")
    card_search_ui.search_by_name.__wrapped__(return_to)
    card_search_ui.card_search_menu.assert_called_with(return_to)

    input_cls.return_value.show.return_value = "blue"
    mocker.patch("ui.card_search_ui.show_search_results")
    card_search_ui.search_by_name.__wrapped__(return_to)
    card_search_ui.show_search_results.assert_called_with(return_to, name_query="blue")

    input_cls.return_value.show.return_value = ""
    card_search_ui.search_by_description.__wrapped__(return_to)
    card_search_ui.card_search_menu.assert_called_with(return_to)

    input_cls.return_value.show.return_value = "destroy"
    card_search_ui.search_by_description.__wrapped__(return_to)
    card_search_ui.show_search_results.assert_called_with(return_to, description_query="destroy")


def test_advanced_search_collects_all_filters(mocker):
    card_search_ui = _patch_card_search(mocker)
    return_to = MagicMock()
    input_cls = mocker.patch("ui.card_search_ui.InputUI")
    input_cls.return_value.show.side_effect = ["name", "desc", "monster", "dark", "dragon"]
    mocker.patch("ui.card_search_ui.show_search_results")

    card_search_ui.advanced_search.__wrapped__(return_to)

    card_search_ui.show_search_results.assert_called_with(
        return_to,
        name_query="name",
        description_query="desc",
        type_query="monster",
        attribute_query="dark",
        race_query="dragon",
    )


def test_search_cards_builds_filters(mocker):
    card_search_ui = _patch_card_search(mocker)
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [(1, "Blue-Eyes")]
    card_search_ui.variables.LANGUAGE_HANDLER.primary_database = db

    rows = card_search_ui._search_cards("blue", "destroy", "monster", "light", "dragon", limit=25)

    assert rows == [(1, "Blue-Eyes")]
    sql, params = db.execute.call_args.args
    assert "texts.name LIKE ? COLLATE NOCASE" in sql
    assert "texts.desc LIKE ? COLLATE NOCASE" in sql
    assert "(datas.type & ?) != 0" in sql
    assert "(datas.attribute & ?) != 0" in sql
    assert "(datas.race & ?) != 0" in sql
    assert params[0] == "%blue%"
    assert params[1] == "%destroy%"
    assert params[-1] == 25


def test_unknown_filter_raises(mocker):
    card_search_ui = _patch_card_search(mocker)

    with pytest.raises(ValueError):
        card_search_ui._search_cards(type_query="not-a-type")
    with pytest.raises(ValueError):
        card_search_ui._search_cards(attribute_query="not-attribute")
    with pytest.raises(ValueError):
        card_search_ui._search_cards(race_query="not-race")

    assert card_search_ui._resolve_filter("", card_search_ui.TYPE_FILTERS, "{value}") is None


def test_show_results_and_read_detail(mocker):
    card_search_ui = _patch_card_search(mocker)
    return_to = MagicMock()
    mocker.patch("ui.card_search_ui._search_cards", return_value=[(10, "Alpha")])
    mocker.patch("ui.card_search_ui._format_card_summary", return_value="monster")
    browser_cls = mocker.patch("ui.card_search_ui.CardSearchResultsUI", side_effect=lambda return_to, rows: ("browser", return_to, rows))

    menu = card_search_ui.show_search_results.__wrapped__(return_to, name_query="alpha")

    assert menu == ("browser", return_to, [(10, "Alpha")])
    browser_cls.assert_called_once_with(return_to, [(10, "Alpha")])

    card_cls = mocker.patch("ui.card_details_ui.Card")
    card_cls.return_value.__str__.return_value = "Card detail"
    card_search_ui.read_card_detail(10)
    card_search_ui.utils.output.assert_called_with("Card detail")


def test_search_cards_uses_translated_catalog(mocker):
    card_search_ui = _patch_card_search(mocker)
    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        (1, "Blue-Eyes White Dragon", "English description"),
        (2, "Dark Magician", "Spellcaster"),
    ]
    card_search_ui.variables.LANGUAGE_HANDLER.primary_database = db
    card_search_ui.variables.LANGUAGE_HANDLER.get_card_translations.return_value = {
        1: {"name": "Dragon Blanc Aux Yeux Bleus", "desc": "Description francaise"},
        2: {"name": "Magicien Sombre", "desc": "Magicien"},
    }

    rows = card_search_ui._search_cards("dragon blanc", "francaise", limit=10)

    assert rows == [(1, "Dragon Blanc Aux Yeux Bleus")]
    sql, params = db.execute.call_args.args
    assert "texts.name LIKE" not in sql
    assert params == ()


def test_card_detail_reader_line_navigation(mocker):
    card_search_ui = _patch_card_search(mocker)
    reader = card_search_ui.CardDetailReaderUI.__new__(card_search_ui.CardDetailReaderUI)
    reader.lines = ["Name", "Stats", "Effect"]
    reader.current_line = 0
    reader.detail_text = "Name\nStats\nEffect"
    reader.line_label = MagicMock()
    reader.details = MagicMock()

    reader.update_line(announce=True)
    assert "1 of 3: Name" in reader.line_label.SetLabel.call_args.args[0]
    card_search_ui.utils.output.assert_called_with("1 of 3: Name")

    reader.move_line(1)
    assert reader.current_line == 1
    assert "2 of 3: Stats" in reader.line_label.SetLabel.call_args.args[0]

    reader.move_line(-1)
    assert reader.current_line == 0

    reader.read_all()
    card_search_ui.utils.output.assert_called_with("Name\nStats\nEffect")


def test_card_result_enter_opens_detail_and_space_reads_all(mocker):
    card_search_ui = _patch_card_search(mocker)
    result_ui = card_search_ui.CardSearchResultsUI.__new__(card_search_ui.CardSearchResultsUI)
    result_ui.cards = [(10, "Alpha")]
    result_ui.current_index = 0
    stack = MagicMock()
    mocker.patch("ui.card_search_ui.utils.get_ui_stack", return_value=stack)
    detail_cls = mocker.patch("ui.card_search_ui.CardDetailReaderUI", return_value="detail-ui")
    mocker.patch("ui.card_search_ui._get_card_detail_text", return_value="all details")

    result_ui.open_current_detail()

    detail_cls.assert_called_once_with(10, "Alpha")
    stack.push_ui.assert_called_once_with("detail-ui")

    result_ui.read_current_detail()
    card_search_ui.utils.output.assert_called_with("all details")


def test_card_search_results_ui_real_wx_navigation(mocker):
    card_search_ui = _patch_card_search(mocker)
    _app, frame = _wx_frame()
    mocker.patch("ui.card_search_ui.utils.get_ui_stack", return_value=frame)
    mocker.patch("ui.card_search_ui._format_card_summary", side_effect=lambda code: f"summary {code}")
    mocker.patch("ui.card_search_ui._get_card_detail_text", side_effect=lambda code: f"Card {code}\nLine two")

    ui = card_search_ui.CardSearchResultsUI(MagicMock(), [(10, "Alpha"), (20, "Beta")])
    try:
        assert ui.result_list.GetCount() == 2
        assert ui.current_index == 0
        assert "Alpha" in ui.summary.GetLabel()

        ui.move_selection(1)
        assert ui.current_index == 1
        assert "Beta" in ui.summary.GetLabel()
        card_search_ui.utils.output.assert_any_call("2 of 2: Beta, summary 20")

        ui.move_selection(-1)
        assert ui.current_index == 0

        ui.read_current_detail()
        card_search_ui.utils.output.assert_any_call("Card 10\nLine two")

        detail_cls = mocker.patch("ui.card_search_ui.CardDetailReaderUI", return_value="detail")
        ui.open_current_detail()
        detail_cls.assert_called_with(10, "Alpha")
        frame.push_ui.assert_called_with("detail")
    finally:
        ui.Destroy()
        frame.Destroy()


def test_card_detail_reader_ui_real_wx_keyboard_and_buttons(mocker):
    card_search_ui = _patch_card_search(mocker)
    _app, frame = _wx_frame()
    mocker.patch("ui.card_search_ui.utils.get_ui_stack", return_value=frame)
    mocker.patch("ui.card_details_ui.card_detail_text", return_value="Name\nStats\nEffect")

    ui = card_search_ui.CardDetailReaderUI(10, "Alpha")
    try:
        assert ui.current_line == 0
        assert "1 of 3: Name" in ui.line_label.GetLabel()

        ui.move_line(1)
        assert ui.current_line == 1
        assert "2 of 3: Stats" in ui.line_label.GetLabel()

        ui.move_line(-1)
        assert ui.current_line == 0

        ui.read_current_line()
        card_search_ui.utils.output.assert_any_call("1 of 3: Name")

        ui.read_all()
        card_search_ui.utils.output.assert_any_call("Name\nStats\nEffect")

        ui.go_back()
        frame.pop_ui.assert_called()
    finally:
        ui.Destroy()
        frame.Destroy()


def test_card_search_results_keyboard_shortcuts(mocker):
    card_search_ui = _patch_card_search(mocker)
    _app, frame = _wx_frame()
    mocker.patch("ui.card_search_ui.utils.get_ui_stack", return_value=frame)
    mocker.patch("ui.card_search_ui._format_card_summary", side_effect=lambda code: f"summary {code}")
    mocker.patch("ui.card_search_ui._get_card_detail_text", side_effect=lambda code: f"Card {code}")

    ui = card_search_ui.CardSearchResultsUI(MagicMock(), [(10, "Alpha"), (20, "Beta")])
    try:
        ui.on_key_down(FakeKeyEvent(wx.WXK_RIGHT))
        assert ui.current_index == 1
        ui.on_key_down(FakeKeyEvent(wx.WXK_LEFT))
        assert ui.current_index == 0

        ui.on_key_down(FakeKeyEvent(wx.WXK_SPACE))
        card_search_ui.utils.output.assert_any_call("Card 10")

        detail_cls = mocker.patch("ui.card_search_ui.CardDetailReaderUI", return_value="detail")
        ui.on_key_down(FakeKeyEvent(wx.WXK_RETURN))
        detail_cls.assert_called_with(10, "Alpha")
        frame.push_ui.assert_called_with("detail")

        ui.on_key_down(FakeKeyEvent(wx.WXK_F1))
        assert "Card results." in card_search_ui.utils.output.call_args.args[0]

        mocker.patch("ui.card_search_ui.card_search_menu")
        ui.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))
        card_search_ui.card_search_menu.assert_called_once()

        unknown = FakeKeyEvent(ord("Z"))
        ui.on_key_down(unknown)
        assert unknown.skipped is True

        ui.result_list.SetSelection(1)
        ui.on_result_selected(None)
        assert ui.current_index == 1
    finally:
        ui.Destroy()
        frame.Destroy()


def test_card_detail_reader_keyboard_shortcuts_and_empty_details(mocker):
    card_search_ui = _patch_card_search(mocker)
    _app, frame = _wx_frame()
    mocker.patch("ui.card_search_ui.utils.get_ui_stack", return_value=frame)
    mocker.patch("ui.card_details_ui.card_detail_text", return_value="\n")

    ui = card_search_ui.CardDetailReaderUI(10, "Alpha")
    try:
        assert ui.lines == ["No details."]
        ui.on_key_down(FakeKeyEvent(wx.WXK_DOWN))
        assert ui.current_line == 0
        ui.on_key_down(FakeKeyEvent(wx.WXK_UP))
        assert ui.current_line == 0
        ui.on_key_down(FakeKeyEvent(wx.WXK_HOME))
        assert ui.current_line == 0
        ui.on_key_down(FakeKeyEvent(wx.WXK_END))
        assert ui.current_line == 0

        ui.on_key_down(FakeKeyEvent(wx.WXK_RETURN))
        card_search_ui.utils.output.assert_any_call("\n")
        ui.on_key_down(FakeKeyEvent(wx.WXK_SPACE))
        card_search_ui.utils.output.assert_any_call("\n")

        ui.on_key_down(FakeKeyEvent(wx.WXK_F1))
        assert "Card details." in card_search_ui.utils.output.call_args.args[0]

        ui.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))
        frame.pop_ui.assert_called()

        unknown = FakeKeyEvent(ord("Z"))
        ui.on_key_down(unknown)
        assert unknown.skipped is True
    finally:
        ui.Destroy()
        frame.Destroy()


def test_card_search_empty_navigation_and_translation_helpers(mocker):
    card_search_ui = _patch_card_search(mocker)

    result_ui = card_search_ui.CardSearchResultsUI.__new__(card_search_ui.CardSearchResultsUI)
    result_ui.cards = []
    result_ui.move_selection(1)
    assert result_ui.cards == []

    reader = card_search_ui.CardDetailReaderUI.__new__(card_search_ui.CardDetailReaderUI)
    reader.lines = []
    reader.current_line = 0
    reader.move_line(1)
    assert reader.current_line == 0

    card_search_ui.variables.LANGUAGE_HANDLER.get_card_translations.return_value = []
    assert card_search_ui._get_card_translations() == {}

    card_search_ui.variables.LANGUAGE_HANDLER.get_card_translation.return_value = {"name": "Translated"}
    assert card_search_ui._translated_result_row(1, "Fallback") == (1, "Translated")

    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [
        (1, "B", "english desc"),
        (2, "A", "filtered out"),
        (3, "C", "match"),
    ]
    translations = {1: {"name": "Beta", "desc": "translated match"}, 2: {"name": "Alpha", "desc": "nope"}}
    rows = card_search_ui._search_cards_with_translations(
        db,
        translations,
        description_query="match",
        type_query="monster",
        attribute_query="light",
        race_query="dragon",
        limit=5,
    )
    assert rows == [(1, "Beta"), (3, "C")]
    sql, params = db.execute.call_args.args
    assert "datas.type" in sql
    assert "datas.attribute" in sql
    assert "datas.race" in sql
    assert len(params) == 3


def test_show_results_error_and_card_summaries(mocker):
    from game.card import card_constants

    card_search_ui = _patch_card_search(mocker)
    return_to = MagicMock()
    mocker.patch("ui.card_search_ui._search_cards", side_effect=ValueError("bad filter"))
    mocker.patch("ui.card_search_ui.card_search_menu")
    assert card_search_ui.show_search_results.__wrapped__(return_to) is None
    card_search_ui.utils.output.assert_called_with("bad filter")

    card_cls = mocker.patch("ui.card_search_ui.Card")
    card = MagicMock()
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.EXTRA | card_constants.TYPE.PENDULUM | card_constants.TYPE.LINK
    card.attack = 2500
    card.defense = 2000
    card_cls.return_value = card
    summary = card_search_ui._format_card_summary(1)
    assert "monster" in summary
    assert "extra deck" in summary
    assert "ATK 2500 DEF 2000" in summary

    card.type = card_constants.TYPE.SPELL
    assert card_search_ui._format_card_summary(2) == "spell"
    card.type = card_constants.TYPE.TRAP
    assert card_search_ui._format_card_summary(3) == "trap"
    card.type = 0
    assert card_search_ui._format_card_summary(4) == "unknown type"
    card_cls.side_effect = Exception("missing")
    assert card_search_ui._format_card_summary(5) == "unknown card"


def test_no_results_returns_to_menu(mocker):
    card_search_ui = _patch_card_search(mocker)
    return_to = MagicMock()
    mocker.patch("ui.card_search_ui._search_cards", return_value=[])
    mocker.patch("ui.card_search_ui.card_search_menu")

    assert card_search_ui.show_search_results.__wrapped__(return_to) is None
    card_search_ui.card_search_menu.assert_called_with(return_to)
