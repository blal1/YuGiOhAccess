from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from tests.test_ui_flows_more import FakeMenu, FakeStatus


def _client():
    client = MagicMock()
    client.memory = SimpleNamespace(
        users_info=[],
        is_host=True,
        room_password="pw",
    )
    client.room = SimpleNamespace(
        roomid=12,
        needpass=True,
        roomnotes="notes",
        banlist_hash=0,
        users=[{"name": "Alice", "pos": 0}],
    )
    client.server = MagicMock()
    return client


def _patch_room_ui(mocker, tmp_path):
    from ui import room_ui

    mocker.patch("ui.room_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.room_ui.DynamicVerticalMenu", FakeMenu)
    mocker.patch("ui.room_ui.StatusMessage", FakeStatus)
    mocker.patch("ui.room_ui.utils.get_ui_stack", return_value=MagicMock())
    mocker.patch("ui.room_ui.utils.output")
    mocker.patch("ui.room_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    room_ui.variables.DEV_OPTIONS = SimpleNamespace(deck=None, bot=False, botdeck=None)
    room_ui.variables.DECK_DIR = tmp_path
    room_ui.variables.LOCAL_DATA_DIR = tmp_path
    banlist = MagicMock()
    banlist.name = "No limits"
    banlist.is_deck_allowed.return_value = (True, {})
    manager = mocker.patch("ui.room_ui.banlists.BanlistManager")
    manager.return_value.get_banlist_by_hash.return_value = banlist
    return room_ui, banlist


def test_room_packet_handlers_and_display(mocker, tmp_path):
    from game.edo import structs
    from ui import room_ui

    room_ui, _ = _patch_room_ui(mocker, tmp_path)
    client = _client()

    create = structs.StocCreateGame()
    create.id = 42
    room_ui.handle_create_game(client, bytes(create), len(bytes(create)))
    assert room_ui.utils.output.called

    enter = structs.StocPlayerEnter()
    enter.name = (ord("B"), ord("o"), ord("b"), 0)
    enter.pos = 1
    room_ui.handle_player_enter(client, bytes(enter), len(bytes(enter)))
    assert client.memory.users_info[-1]["name"].startswith("Bob")

    network_enter = "WindBot".encode("utf-16-le").ljust(40, b"\x00") + b"\x01"
    room_ui.handle_player_enter(client, network_enter, len(network_enter))
    assert client.memory.users_info[-1] == {"name": "WindBot", "ready": False, "host": False, "position": 1}
    assert room_ui._parse_player_enter_packet(network_enter) == ("WindBot", 1)
    with pytest.raises(ValueError, match="PLAYER_ENTER packet too short"):
        room_ui._parse_player_enter_packet(b"x")

    change = structs.StocPlayerChange()
    change.status = 0x10 | 1
    room_ui.handle_player_change(client, bytes(change), len(bytes(change)))
    room_ui.handle_type_change(client, bytes(change), len(bytes(change)))
    assert client.what_player_am_i == 1
    change.status = int(structs.StocChangeType.SPECTATE)
    room_ui.handle_player_change(client, bytes(change), len(bytes(change)))
    assert "spectating" in room_ui.utils.output.call_args.args[0]

    client.memory.users_info = [{"name": "Alice", "ready": True, "host": True, "position": 0}, {"name": "Gone", "ready": False, "host": False, "position": 1}]
    players = room_ui.resolve_players(client)
    assert "Alice" in players
    assert "Gone" not in players

    menu = room_ui.display_room_menu.__wrapped__(client)
    assert any("Room ID" in str(item[0]) for item in menu.items)

    del client.room.banlist_hash
    client.room.lflist = 0
    menu = room_ui.display_room_menu.__wrapped__(client)
    assert any("Banlist" in str(item[0]) for item in menu.items)

    room_ui.banlists.BanlistManager.return_value.get_banlist_by_hash.return_value = None
    client.room.lflist = 540476041
    menu = room_ui.display_room_menu.__wrapped__(client)
    assert any("Unknown banlist" in str(item[0]) for item in menu.items)

    client.room.team1 = 2
    client.room.team2 = 2
    client.room.best_of = 3
    client.room.users = [
        {"name": "Alice", "pos": 0},
        {"name": "Bob", "pos": 1},
        {"name": "Carol", "pos": 2},
        {"name": "Dave", "pos": 3},
    ]
    client.memory.users_info = [
        {"name": "Alice", "ready": True, "host": True, "position": 0},
        {"name": "Bob", "ready": False, "host": False, "position": 1},
        {"name": "Carol", "ready": False, "host": False, "position": 2},
        {"name": "Dave", "ready": False, "host": False, "position": 3},
    ]
    menu = room_ui.display_room_menu.__wrapped__(client)
    assert any("Tag duel 2 vs 2" in str(item[0]) for item in menu.items)
    assert any("Side decking is available" in str(item[0]) for item in menu.items)
    players = room_ui.resolve_players(client)
    assert "Team 1 slot 1 - Alice" in players
    assert "Team 1 slot 2 - Bob" in players
    assert "Team 2 slot 1 - Carol" in players
    assert "Team 2 slot 2 - Dave" in players

    client.room = None
    menu = room_ui.display_room_menu.__wrapped__(client)
    assert any("Room information could not be loaded" in str(item[0]) for item in menu.items)


def test_room_join_dev_options_and_fallback_helpers(mocker, tmp_path):
    from game.edo import structs

    room_ui, _ = _patch_room_ui(mocker, tmp_path)
    client = _client()
    client.memory.room_password = None
    create = structs.StocCreateGame()
    create.id = 7
    delattr(client.memory, "room_password")
    room_ui.handle_create_game(client, bytes(create), len(bytes(create)))
    assert "Created room with ID 7" in room_ui.utils.output.call_args.args[0]

    deck_file = tmp_path / "Auto.json"
    deck_file.write_text("{}")
    room_ui.variables.DEV_OPTIONS = SimpleNamespace(deck="Auto", bot=True, botdeck="botdeck")
    select = mocker.patch("ui.room_ui.handle_deck_menu_select_deck")
    add_bot = mocker.patch("ui.room_ui.add_bot_to_room")
    display = mocker.patch("ui.room_ui.display_room_menu", return_value="menu")

    assert room_ui.handle_join_game(client, b"", 0) == "menu"

    select.assert_called_once_with(client, deck_file)
    add_bot.assert_called_once_with(client, "Botdeck")
    display.assert_called_once_with(client)
    assert client.memory.users_info == []

    room_ui.variables.DEV_OPTIONS = SimpleNamespace(deck="Missing", bot=True, botdeck=None)
    room_ui.handle_join_game(client, b"", 0)
    add_bot.assert_called_with(client)
    assert "Deck Missing not found" in room_ui.utils.output.call_args_list[-1].args[0]

    room = SimpleNamespace(team1="bad", team2="bad", host_info=SimpleNamespace(t0_count=2, t1_count=3))
    assert room_ui._room_capacity(room) == 5
    assert room_ui._team_label_for_position(room, "observer") == "Team observer"
    room.host_info = {"t0_count": 4, "t1_count": 5, "banlist_hash": "123"}
    assert room_ui._room_capacity(room) == 9
    assert room_ui._room_banlist_hash(room) == 123
    room.host_info = {"lflist": "456"}
    assert room_ui._room_banlist_hash(room) == 456
    room.host_info = {"lflist": "bad"}
    assert room_ui._room_banlist_hash(room) == 0
    assert room_ui._team_label_for_position(SimpleNamespace(team1=1, team2=1), 5) == "Spectator"

    spectator_client = _client()
    spectator_client.room.users = [{"name": "Watcher", "pos": 3}]
    spectator_client.memory.users_info = [{"name": "Watcher", "ready": False, "host": False, "position": 3, "spectator": True}]
    assert "Spectator - Watcher" in room_ui.resolve_players(spectator_client)


def test_room_ready_and_deck_menus(mocker, tmp_path):
    room_ui, banlist = _patch_room_ui(mocker, tmp_path)
    client = _client()

    room_ui.handle_room_menu_ready_or_start(client)
    assert FakeStatus.shown

    client.memory.deck = MagicMock()
    room_ui.handle_room_menu_ready_or_start(client)
    from game.edo import structs
    client.send.assert_any_call(structs.ClientIdType.READY)
    client.send.assert_any_call(structs.ClientIdType.TRY_START)

    select_menu = room_ui.handle_room_menu_select_deck.__wrapped__(client)
    assert any(item[0] == "Public Decks" for item in select_menu.items)

    deck_dir = tmp_path / "decks"
    deck_dir.mkdir()
    (deck_dir / "test.json").write_text("{}")
    (deck_dir / "ignore.txt").write_text("x")
    deck_menu = room_ui.handle_room_menu_show_deck_menu.__wrapped__(client, "Decks", deck_dir)
    assert any(item[0] == "test" for item in deck_menu.items)
    assert not any(item[0] == "ignore" for item in deck_menu.items)

    parsed = MagicMock(cards=[1, 2], side=[3])
    mocker.patch("ui.room_ui.ydke.Deck.from_json", return_value=parsed)

    check_menu = room_ui.handle_room_menu_check_deck_against_banlist.__wrapped__(client)
    assert any(item[0] == "My Decks" for item in check_menu.items)
    banlist_deck_menu = room_ui.handle_room_menu_show_banlist_deck_menu.__wrapped__(client, "Decks", deck_dir)
    assert any(item[0] == "test" for item in banlist_deck_menu.items)
    result_menu = room_ui.show_room_banlist_check_result.__wrapped__(client, deck_dir / "test.json")
    assert any("legal" in str(item[0]) for item in result_menu.items)

    mocker.patch("ui.room_ui.display_room_menu")
    room_ui.handle_deck_menu_select_deck.__wrapped__(client, deck_dir / "test.json")
    assert client.memory.parsed_deck is parsed

    banlist.is_deck_allowed.return_value = (False, {1: SimpleNamespace(limit=1, found=3)})
    card_cls = mocker.patch("ui.room_ui.Card")
    card_cls.return_value.name = "Limited"
    card_cls.return_value.get_name.return_value = "Limited"
    result_menu = room_ui.show_room_banlist_check_result.__wrapped__(client, deck_dir / "test.json")
    assert any("Limited" in str(item[0]) for item in result_menu.items)

    banned = room_ui.handle_deck_menu_select_deck.__wrapped__(client, deck_dir / "test.json")
    assert any("Limited" in str(item[0]) for item in banned.items)

    missing_dir = tmp_path / "missing_decks"
    created_menu = room_ui.handle_room_menu_show_deck_menu.__wrapped__(client, "Created", missing_dir)
    assert missing_dir.exists()
    assert any(item[0] == "Back" for item in created_menu.items)

    empty_banlist_dir = tmp_path / "empty_banlist"
    empty_menu = room_ui.handle_room_menu_show_banlist_deck_menu.__wrapped__(client, "Empty", empty_banlist_dir)
    assert any(item[0] == "No decks found." for item in empty_menu.items)


def test_import_decks_and_single_deck_validation(mocker, tmp_path):
    room_ui, _ = _patch_room_ui(mocker, tmp_path)
    client = _client()

    menu = room_ui.handle_import_all_decks.__wrapped__(client)
    assert any(item[3].get("label") == "Username" for item in menu.items)

    for username, password in [("", "pw"), ("user", "")]:
        room_ui.handle_import_all_decks_import(client, username, password)
        assert FakeStatus.shown

    response = MagicMock(status_code=500)
    response.json.return_value = {"error": "bad"}
    mocker.patch("ui.room_ui.requests.post", return_value=response)
    room_ui.handle_import_all_decks_import(client, "user", "pw")

    response.status_code = 200
    response.json.return_value = []
    room_ui.handle_import_all_decks_import(client, "user", "pw")

    response.json.return_value = [{"name": "Bad:Name", "url": "ydke://deck"}]
    deck = MagicMock()
    deck.to_json.return_value = "{}"
    mocker.patch("ui.room_ui.ydke.Deck.from_ydke", return_value=deck)
    room_ui.handle_import_all_decks_import(client, "user", "pw")
    assert (tmp_path / "Bad_Name.json").exists()

    # A side effect that writes an extra file makes the imported count differ from the server count.
    def write_extra_file():
        (tmp_path / "extra.json").write_text("{}")
        return "{}"

    deck.to_json.side_effect = write_extra_file
    response.json.return_value = [{"name": "OnlyOne", "url": "ydke://deck"}]
    room_ui.handle_import_all_decks_import(client, "user", "pw")
    assert FakeStatus.shown
    deck.to_json.side_effect = None
    deck.to_json.return_value = "{}"

    import_menu = room_ui.handle_import_deck_show_menu.__wrapped__(client)
    assert any(item[3].get("label") == "Deck name" for item in import_menu.items)

    for name, deck_string in [("", "ydke://x"), ("Good", ""), ("Good", "notydke")]:
        room_ui.handle_deck_import_import_deck(client, name, deck_string)
        assert FakeStatus.shown

    sanitize_patch = mocker.patch("ui.room_ui.utils.sanitize_filename", return_value=" ")
    room_ui.handle_deck_import_import_deck(client, ":::", "ydke://x")
    assert FakeStatus.shown
    mocker.stop(sanitize_patch)

    mocker.patch("ui.room_ui.ydke.Deck.from_ydke", side_effect=room_ui.ydke.URLParseError("bad"))
    room_ui.handle_deck_import_import_deck(client, "Invalid", "ydke://bad")
    assert FakeStatus.shown

    mocker.patch("ui.room_ui.ydke.Deck.from_ydke", return_value=deck)

    ydke_file = tmp_path / "loaded.ydke"
    ydke_file.write_text("ydke://loaded")
    assert room_ui._load_deck_file(ydke_file) is deck

    room_ui.handle_deck_import_import_deck(client, "Bad Name", "ydke://x")
    assert (tmp_path / "Bad_Name.json").exists()

    room_ui.handle_deck_import_import_deck(client, "Good", "ydke://x")
    assert (tmp_path / "Good.json").exists()


def test_bot_and_disconnect_paths(mocker, tmp_path):
    room_ui, _ = _patch_room_ui(mocker, tmp_path)
    client = _client()

    mocker.patch("ui.room_ui._get_available_bot_decks", return_value=[])
    room_ui.handle_add_bot_as_opponent(client)
    assert FakeStatus.shown

    client.room.users = [{"name": "A"}, {"name": "B"}]
    room_ui.handle_add_bot_as_opponent(client)
    assert FakeStatus.shown

    client.room.users = [{"name": "A"}]

    mocker.patch("ui.room_ui._get_available_bot_decks", return_value=["BotDeck"])
    room_ui.handle_add_bot_as_opponent(client)
    room_ui.utils.get_ui_stack.return_value.push_ui.assert_called()

    client.room.users = [{"name": "A"}, {"name": "B"}]
    room_ui.add_bot_to_room(client)
    assert FakeStatus.shown

    client.room.users = [{"name": "A"}]
    mocker.patch.dict("sys.modules", {"bot.launcher": MagicMock(launch_bot_for_room=MagicMock())})
    mocker.patch("ui.room_ui.display_room_menu", return_value="room")
    assert room_ui.add_bot_to_room(client, available_decks=["BotDeck"]) == "room"

    failing_launcher = MagicMock(launch_bot_for_room=MagicMock(side_effect=RuntimeError("boom")))
    mocker.patch.dict("sys.modules", {"bot.launcher": failing_launcher})
    room_ui.add_bot_to_room(client, deck="BotDeck")
    assert FakeStatus.shown

    mocker.patch("ui.room_ui.server_ui.server_main_menu", return_value="server")
    assert room_ui.handle_me_disconnect(client) == "server"
    client.disconnect.assert_called_once()


def test_get_available_bot_decks_missing_directory(mocker, tmp_path):
    room_ui, _ = _patch_room_ui(mocker, tmp_path)
    fake_file = tmp_path / "root" / "src" / "ui" / "room_ui.py"
    fake_file.parent.mkdir(parents=True)
    mocker.patch.object(room_ui, "__file__", str(fake_file))

    assert room_ui._get_available_bot_decks() == []

    decks_dir = tmp_path / "root" / "Decks"
    decks_dir.mkdir()
    # Only decks a bundled executor can actually pilot are offered now.
    (decks_dir / "AI_Blackwing.ydk").write_text("deck")
    (decks_dir / "Bot.ydk").write_text("deck")
    (decks_dir / "Nope.txt").write_text("no")
    assert room_ui._get_available_bot_decks() == ["Blackwing"]
