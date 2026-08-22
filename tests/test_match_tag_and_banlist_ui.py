from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.test_ui_flows_more import FakeMenu


def test_create_room_sets_match_and_tag_host_info(mocker):
    from game.client import Client
    from game.edo import structs

    client = Client.__new__(Client)
    client.memory = SimpleNamespace()
    client._connect = MagicMock()
    client.send = MagicMock()
    client.wait_for_packet = MagicMock(return_value=(structs.ServerIdType.CREATE_GAME, 0, bytes(structs.StocCreateGame(id=77))))
    mocker.patch("game.client.Client", return_value=client)
    mocker.patch("game.client.variables.config.get", return_value="Tester")
    banlist = MagicMock(hash=123)
    manager = mocker.patch("game.client.banlists.BanlistManager")
    manager.return_value.get_banlist_by_name.return_value = banlist
    mocker.patch("game.client.variables.DEV_OPTIONS", SimpleNamespace(no_shuffle=False, draw=None))

    created = Client.create_room(MagicMock(), {"name": "n", "password": "", "notes": "", "banlist": "No limits", "best_of": 3, "team_count": 2})

    packet = client.send.call_args_list[1].args[1]
    assert packet.host_info.best_of == 3
    assert packet.host_info.t0_count == 2
    assert packet.host_info.t1_count == 2
    assert created.room_id == 77


def test_deck_editor_banlist_check_menus(mocker):
    from ui import deck_editor_ui

    mocker.patch("ui.deck_editor_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.deck_editor_ui._validate_deck_for_save", return_value=None)
    manager = mocker.patch("ui.deck_editor_ui.banlists.BanlistManager")
    manager.return_value.get_banlist_names.return_value = ["TCG"]
    legal = MagicMock()
    legal.is_deck_allowed.return_value = (True, {})
    manager.return_value.get_banlist_by_name.return_value = legal

    menu = deck_editor_ui.check_deck_against_banlist.__wrapped__("Deck", {"main": [1], "side": []}, lambda: None)
    assert any(item[0] == "TCG" for item in menu.items)

    result = deck_editor_ui.show_banlist_check_result.__wrapped__("Deck", {"main": [1], "side": []}, "TCG", lambda: None)
    assert any("legal" in str(item[0]) for item in result.items)

    illegal = MagicMock(limit=1, found=3)
    legal.is_deck_allowed.return_value = (False, {1: illegal})
    card_cls = mocker.patch("ui.deck_editor_ui.Card")
    card_cls.return_value.get_name.return_value = "Limited Card"
    result = deck_editor_ui.show_banlist_check_result.__wrapped__("Deck", {"main": [1], "side": []}, "TCG", lambda: None)
    assert any("Limited Card" in str(item[0]) for item in result.items)
