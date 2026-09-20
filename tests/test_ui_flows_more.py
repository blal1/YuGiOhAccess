from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class FakeMenu:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.items = []
        self.help_text = ""
        self.codes_by_row = {}

    def append_item(self, option, function=None, *args, **kwargs):
        control = MagicMock()
        control.GetValue.return_value = kwargs.get("label", "")
        control.GetSelection.return_value = 0
        control.GetString.return_value = "Banlist"
        control.GetCurrentSelection.return_value = 0
        self.items.append((option, function, args, kwargs, control))
        return control

    def append_card(self, code, label, function=None):
        """Stand-in for ui.card_details_ui.CardChoiceMenu.append_card."""
        control = self.append_item(str(label), function)
        self.codes_by_row[len(self.items) - 1] = code
        return control

    def set_help_text(self, text):
        self.help_text = text

    def show(self):
        return None


class FakeStatus(FakeMenu):
    shown = []

    def __init__(self, message, call_after=None, *args, **kwargs):
        super().__init__(message, call_after, *args, **kwargs)
        self.message = message
        self.call_after = call_after

    def show(self):
        self.shown.append(self.message)


def _patch_common_ui(mocker, module_name):
    mocker.patch(f"{module_name}.VerticalMenu", FakeMenu)
    if hasattr(__import__(module_name, fromlist=["x"]), "StatusMessage"):
        mocker.patch(f"{module_name}.StatusMessage", FakeStatus)
    stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=stack)
    mocker.patch("core.utils.output")
    return stack


def test_main_menus_and_settings_callbacks(mocker):
    from ui import main_ui

    _patch_common_ui(mocker, "ui.main_ui")
    mocker.patch("ui.main_ui.InputUI")
    mocker.patch("ui.main_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    mocker.patch("ui.main_ui.utils.version_string_to_pretty", return_value="1.0")
    mocker.patch("ui.main_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    main_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None)
    main_ui.variables.IS_FROZEN = False
    main_ui.variables.APP_VERSION = "1.0"
    main_ui.variables.config = MagicMock()
    main_ui.variables.config.get.side_effect = lambda key, default=None: {
        "nickname": "Tester",
        "first_time_run": False,
        "enable_hints": True,
        "screenreader_output_only_on_application_focus": False,
        "helper_zones": True,
        "rock_paper_scissors_bot_behavior": "paper",
        "enable_bot_chat": True,
        "ui_language": "en",
    }.get(key, default)
    menu = main_ui.main_menu_view.__wrapped__()
    assert any(item[0] == "Deck Editor" for item in menu.items)
    assert any("Play" in item[0] for item in menu.items)

    help_menu = main_ui.help_menu_view.__wrapped__()
    assert len(help_menu.items) == 3

    first_menu = main_ui.first_ui_help_info.__wrapped__(main_ui.main_menu_view)
    assert len(first_menu.items) > 10

    slider_event = MagicMock()
    slider_event.GetEventObject.return_value.GetValue.return_value = 7
    main_ui.on_music_volume_change(slider_event)
    main_ui.on_sound_effects_volume_change(slider_event)
    main_ui.variables.config.set.assert_any_call("music_volume", main_ui.utils.get_ui_stack().music_audio_manager.get_volume.return_value)
    main_ui.variables.config.set.assert_any_call("sound_effects_volume", main_ui.utils.get_ui_stack().sound_effects_audio_manager.get_volume.return_value)

    choice_event = MagicMock()
    for idx, expected in enumerate(["random", "rock", "paper", "scissors"]):
        choice_event.GetEventObject.return_value.GetCurrentSelection.return_value = idx
        main_ui.on_rock_paper_scissors_bot_behavior_change(choice_event)
        main_ui.variables.config.set.assert_any_call("rock_paper_scissors_bot_behavior", expected)


def test_change_nickname_and_windbot_clipboard(mocker):
    from ui import main_ui

    _patch_common_ui(mocker, "ui.main_ui")
    mocker.patch("ui.main_ui.main_menu_view", return_value="main")
    input_cls = mocker.patch("ui.main_ui.InputUI")
    input_cls.return_value.show.return_value = "NewName"
    main_ui.variables.config = MagicMock()

    result = main_ui.change_nickname.__wrapped__("OldName")
    assert result == "main"
    main_ui.variables.config.set.assert_called_with("nickname", "NewName")

    input_cls.return_value.show.return_value = ""
    assert main_ui.change_nickname.__wrapped__("OldName") == "main"

    deck = MagicMock()
    deck.to_windbot_format.return_value = "windbot"
    deck.to_ydke.return_value = "ydke"
    mocker.patch("ui.main_ui.Deck.from_ydke", return_value=deck)
    mocker.patch("ui.main_ui.Deck.from_windbot_format", return_value=deck)
    mocker.patch("ui.main_ui.wx.TheClipboard")
    mocker.patch("ui.main_ui.wx.TextDataObject", side_effect=lambda text: text)
    main_ui.save_windbot_deck("Deck", "ydke://x")
    main_ui.save_deck_string_from_windbot_deck("Deck", "1\n2")
    assert main_ui.wx.TheClipboard.SetData.call_count == 2
    assert main_ui.save_windbot_deck("", "") == "main"
    assert main_ui.save_deck_string_from_windbot_deck("", "") == "main"


def test_server_ui_flows(mocker):
    from ui import server_ui

    _patch_common_ui(mocker, "ui.server_ui")
    wait_cls = mocker.patch("ui.server_ui.WaitUI")
    wait_cls.return_value.show.return_value = True
    mocker.patch("ui.server_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    server = MagicMock()
    server.name = "Test"
    server.list_rooms.return_value = []
    server.get_room.return_value = None
    server_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None, action=None, password=None, id=None)

    mocker.patch("ui.server_ui.get_servers", return_value=[server])
    menu = server_ui.server_selection_menu.__wrapped__()
    assert any(item[0] == "Test" for item in menu.items)

    menu = server_ui.server_main_menu.__wrapped__(server)
    assert any(item[0] == "Create Room" for item in menu.items)

    wait_cls.return_value.show.return_value = False
    server_ui.server_main_menu.__wrapped__(server)
    assert FakeStatus.shown

    room = MagicMock()
    room.istart = "waiting"
    room.roomid = 10
    room.needpass = True
    room.roomname = "Room"
    room.roomnotes = "Notes"
    room.team1 = "A"
    room.team2 = "B"
    room.best_of = 3
    room.time_limit = 180
    room.start_lp = 4000
    room.start_hand = 4
    room.draw_count = 2
    room.print_players.return_value = "P1"
    server.list_rooms.return_value = [room, MagicMock(istart="dueling")]
    menu = server_ui.list_rooms.__wrapped__(server)
    assert any("needs password" in item[0] for item in menu.items if isinstance(item[0], str))
    assert any("Duelists:" in item[0] for item in menu.items if isinstance(item[0], str))

    event = MagicMock()
    choice = MagicMock()
    choice.GetSelection.return_value = 0
    choice.GetCount.return_value = 2
    choice.GetString.return_value = "B"
    event.GetKeyCode.return_value = server_ui.wx.WXK_LEFT
    server_ui.banlist_change_choice(event, choice)
    choice.SetSelection.assert_called_with(1)
    event.GetKeyCode.return_value = server_ui.wx.WXK_RIGHT
    server_ui.banlist_change_choice(event, choice)

    mocker.patch("ui.server_ui.Client.create_room", return_value=MagicMock(memory=MagicMock()))
    server_ui.create_room_on_server(server, {"password": "pw"})
    server_ui.Client.create_room.return_value.memory.__setattr__

    room.team1 = "2"
    room.team2 = "2"
    room.users = [{"name": "one", "pos": 0}, {"name": "two", "pos": 1}, {"name": "three", "pos": 7}]
    action_menu = server_ui.room_action_menu.__wrapped__(server, room)
    assert any(item[0] == "Join as duelist" for item in action_menu.items)
    assert server_ui.room_user_count(room) == 2

    server.get_room.return_value = None
    server_ui.join_room(server, 1)
    room.users = [{"name": "one", "pos": 0}, {"name": "two", "pos": 1}, {"name": "three", "pos": 2}, {"name": "four", "pos": 3}]
    server.get_room.return_value = room
    server_ui.join_room(server, 1, "pw")


def test_server_ui_dev_create_join_spectate_and_capacity_edges(mocker):
    from ui import server_ui

    _patch_common_ui(mocker, "ui.server_ui")
    wait_cls = mocker.patch("ui.server_ui.WaitUI")
    wait_cls.return_value.show.return_value = True
    mocker.patch("ui.server_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    mocker.patch("ui.server_ui.utils.output")
    mocker.patch("ui.server_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    server = MagicMock()
    server.name = "Test"
    server_ui.variables.DEV_OPTIONS = SimpleNamespace(server=0, action=None, password=None, id=None)
    mocker.patch("ui.server_ui.get_servers", return_value=[server])
    assert server_ui.server_selection_menu.__wrapped__() is None

    real_join_room_final = server_ui.join_room_final
    mocker.patch("ui.server_ui.create_room_on_server")
    mocker.patch("ui.server_ui.join_room_final")
    server_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None, action="create", password="pw", id=12)
    server_ui.server_main_menu.__wrapped__(server)
    server_ui.create_room_on_server.assert_called()
    server_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None, action="join", password="pw", id=12)
    server_ui.server_main_menu.__wrapped__(server)
    server_ui.join_room_final.assert_called_with(server, 12, "pw")

    banlist_manager = mocker.patch("ui.server_ui.banlists.BanlistManager")
    banlist_manager.return_value.get_banlist_names.return_value = ["tcg"]
    create_menu = server_ui.create_room.__wrapped__(server)
    assert any(item[0] == "Create Room" for item in create_menu.items)
    create_callback = [item[1] for item in create_menu.items if item[0] == "Create Room"][0]
    create_callback()
    server_ui.create_room_on_server.assert_called()

    number_input = mocker.patch("ui.server_ui.NumberInputUI")
    number_input.return_value.show.return_value = None
    server_ui.join_room_ask_for_id(server)
    server_ui.spectate_room_ask_for_id(server)
    assert wait_cls.return_value.show.call_count >= 3
    number_input.return_value.show.return_value = 77
    real_join_room = server_ui.join_room
    real_spectate_room = server_ui.spectate_room
    mocker.patch("ui.server_ui.join_room")
    mocker.patch("ui.server_ui.spectate_room")
    server_ui.join_room_ask_for_id(server)
    server_ui.spectate_room_ask_for_id(server)
    server_ui.join_room.assert_called_with(server, 77)
    server_ui.spectate_room.assert_called_with(server, 77)

    room = MagicMock()
    room.capacity.return_value = "4"
    assert server_ui.room_capacity(room) == 4
    room.capacity.side_effect = TypeError
    room.team1 = "2"
    room.team2 = "2"
    assert server_ui.room_capacity(room) == 4
    room.team1 = "bad"
    room.host_info.t0_count = 1
    room.host_info.t1_count = 2
    assert server_ui.room_capacity(room) == 3
    del room.host_info
    assert server_ui.room_capacity(room) == 2

    room = MagicMock()
    room.duelist_users.return_value = ["a", "b"]
    assert server_ui.room_user_count(room) == 2
    room.duelist_users.side_effect = TypeError
    room.users = [object(), object()]
    assert server_ui.room_user_count(room) == 2

    missing = MagicMock()
    missing.istart = "dueling"
    server.get_room.return_value = missing
    real_join_room(server, 5)
    assert FakeStatus.shown

    room = MagicMock()
    room.istart = "waiting"
    room.needpass = True
    room.roomid = 5
    room.team1 = "1"
    room.team2 = "1"
    room.users = []
    server.get_room.return_value = room
    input_cls = mocker.patch("ui.server_ui.InputUI")
    input_cls.return_value.show.return_value = None
    real_join_room(server, 5)
    real_spectate_room(server, 5)
    assert wait_cls.return_value.show.call_count >= 5

    input_cls.return_value.show.return_value = "pw"
    mocker.patch("ui.server_ui.join_room_final")
    real_join_room(server, 5)
    real_spectate_room(server, 5)
    server_ui.join_room_final.assert_any_call(server, 5, "pw")
    server_ui.join_room_final.assert_any_call(server, 5, "pw", as_observer=True)

    room.needpass = False
    room.users = [{"pos": 0}, {"pos": 1}]
    real_join_room(server, 5)
    assert any("Room is full" in str(message) for message in FakeStatus.shown)

    mocker.patch("ui.server_ui.Client.join_room", return_value=None)
    real_join_room_final(server, 5, "bad")
    assert any("Password incorrect" in str(message) for message in FakeStatus.shown)
    joined = MagicMock()
    mocker.patch("ui.server_ui.Client.join_room", return_value=joined)
    real_join_room_final(server, 5, "pw", as_observer=True)
    assert joined.memory.is_observer is True


def test_data_updater_thread_paths(mocker, tmp_path):
    from ui import data_updater_ui

    _patch_common_ui(mocker, "ui.data_updater_ui")
    mocker.patch("ui.data_updater_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    repo1 = tmp_path / "repo1"
    repo2 = tmp_path / "repo2"
    repo1.mkdir()
    repo2.mkdir()
    (repo1 / "x").write_text("x")
    (repo2 / "x").write_text("x")
    data_updater_ui.variables.DATA_REPOSITORIES = [{"name": "a", "url": "u", "local_path": repo1}, {"name": "b", "url": "u", "local_path": repo2}]
    assert data_updater_ui._has_cached_data() is True
    (repo2 / "x").unlink()
    assert data_updater_ui._has_cached_data() is False

    mocker.patch("ui.data_updater_ui.threading.Thread")
    menu = data_updater_ui.ensure_yugioh_data_is_up_to_date.__wrapped__()
    assert menu.items

    fail = data_updater_ui.failed_data_update.__wrapped__()
    assert any(item[0] == "Retry" for item in fail.items)

    mocker.patch("ui.data_updater_ui.RESULT_UI")
    data_updater_ui._warn_cached_then_continue.__wrapped__()
    data_updater_ui.RESULT_UI.assert_called_once()


def test_side_deck_pick_view_submit(mocker):
    from ui import side_deck_ui

    _patch_common_ui(mocker, "ui.side_deck_ui")
    card_cls = mocker.patch("ui.side_deck_ui.Card")
    card_cls.return_value.get_name.return_value = "Card"
    client = MagicMock()
    client.memory.deck = MagicMock()
    client.memory.parsed_deck.cards = [1, 1, 2]
    client.memory.parsed_deck.side = [3]

    side_deck_ui.show_side_deck_ui(client)
    side_deck_ui.utils.get_ui_stack.return_value.push_ui.assert_called()

    main_cards = [1, 1, 2]
    side_cards = [3]
    menu = side_deck_ui._pick_from_main.__wrapped__(client, main_cards, side_cards, [], [])
    assert any("x2" in item[0] for item in menu.items if isinstance(item[0], str))

    menu = side_deck_ui._pick_from_side.__wrapped__(client, main_cards, side_cards, [], [])
    assert menu.items

    empty = side_deck_ui._pick_from_side.__wrapped__(client, main_cards, [], [], [])
    assert empty is None

    swaps = side_deck_ui._view_swaps.__wrapped__(client, main_cards, side_cards, [1], [3])
    assert any("side" in item[0] for item in swaps.items if isinstance(item[0], str))

    side_deck_ui._submit_side_deck(client, main_cards, side_cards)
    assert client.send.called

    client2 = MagicMock()
    del client2.memory.deck
    side_deck_ui.show_side_deck_ui(client2)
    side_deck_ui.utils.output.assert_called()
