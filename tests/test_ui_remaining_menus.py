from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.test_duel_messages_simple_more import NamedCard, _client
from tests.test_ui_flows_more import FakeMenu, FakeStatus


def test_replay_and_side_deck_remaining_menu_paths(mocker, tmp_path):
    from ui import replay_ui, side_deck_ui

    client, stack = _client(mocker)
    client.room_id = "room"
    mocker.patch("ui.replay_ui.variables.APP_DATA_DIR", tmp_path)
    mocker.patch("ui.replay_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.replay_ui.wx.TheClipboard", MagicMock())
    mocker.patch("ui.replay_ui.wx.TextDataObject", side_effect=lambda value: value)

    empty_menu = replay_ui.replay_viewer_menu.__wrapped__()
    assert empty_menu.items[0][0] == "No saved duels yet."

    replay_file = replay_ui.save_replay_packet(client, b"abc", new=True)
    menu = replay_ui.replay_info_menu.__wrapped__(replay_file)
    assert menu.items[0][0].startswith("Replay file:")
    replay_ui.copy_replay_path(replay_file)
    deleted_menu = replay_ui.delete_replay(replay_file)
    assert deleted_menu.items[0][0] == "No saved duels yet."

    mocker.patch("ui.side_deck_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.side_deck_ui.Card", side_effect=lambda code: NamedCard(f"Card {code}"))
    mocker.patch("ui.side_deck_ui.match_ui.is_match", return_value=True)
    mocker.patch("ui.side_deck_ui.match_ui.score_text", return_value="match score")

    client.memory.deck = None
    side_deck_ui.show_side_deck_ui(client)

    side_deck_ui._show_side_menu(client, [1], [2], [], [])
    pushed = stack.push_ui.call_args.args[0]
    assert pushed.items[0][0] == "match score"

    side_menu = side_deck_ui._pick_from_side.__wrapped__(client, [1], [2, 2], [], [])
    assert "x2" in side_menu.items[0][0]

    side_deck_ui._pick_from_side.__wrapped__(client, [1], [], [], [])
    swap_menu = side_deck_ui._view_swaps.__wrapped__(client, [1], [2], [], [])
    assert swap_menu.items[0][0] == "No swaps made yet."


def test_server_ui_remaining_error_and_room_list_paths(mocker):
    from ui import server_ui

    mocker.patch("ui.server_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.server_ui.StatusMessage", FakeStatus)
    mocker.patch("ui.server_ui.WaitUI", return_value=SimpleNamespace(show=lambda: False))
    server = SimpleNamespace(name="Srv", is_available=lambda: False)
    assert server_ui.server_main_menu.__wrapped__(server) is None

    mocker.patch("ui.server_ui.Client.create_room", return_value=None)
    server_ui.create_room_on_server(server, {"password": ""})

    event = MagicMock()
    event.GetKeyCode.return_value = server_ui.wx.WXK_RIGHT
    choice = MagicMock()
    choice.GetSelection.return_value = 2
    choice.GetCount.return_value = 3
    choice.GetString.return_value = "Wrapped"
    server_ui.banlist_change_choice(event, choice)
    choice.SetSelection.assert_called_with(0)

    server.list_rooms = MagicMock(return_value=[])
    assert server_ui.list_rooms.__wrapped__(server) is None

    room = SimpleNamespace(
        roomid=7,
        istart="waiting",
        needpass=False,
        roomname="Room",
        roomnotes="Notes",
        team1=2,
        team2=2,
        best_of=1,
        users=[{"pos": 0}],
        print_players=lambda: "P1",
        time_limit=180,
        start_lp=8000,
        start_hand=5,
        draw_count=1,
    )
    server.list_rooms.return_value = [room]
    room_menu = server_ui.list_rooms.__wrapped__(server)
    assert "tag duel" in room_menu.items[0][0]
    assert "Duelists: 1/4" in room_menu.items[0][0]

    room.spectator_users = lambda: ["obs"]
    room_menu = server_ui.list_rooms.__wrapped__(server)
    assert "spectators: 1" in room_menu.items[0][0]

    server.get_room = MagicMock(return_value=None)
    server_ui.spectate_room(server, 404)

    client = SimpleNamespace(memory=SimpleNamespace())
    mocker.patch("ui.server_ui.Client.join_room", side_effect=[None, client])
    server_ui.join_room_final(server, 1, "bad")
    server_ui.join_room_final(server, 1, "pw", as_observer=True)
    assert client.memory.is_observer is True
