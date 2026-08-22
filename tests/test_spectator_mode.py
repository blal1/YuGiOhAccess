import ctypes
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_client_join_room_as_observer_sends_to_observer(mocker):
    from game.client import Client
    from game.edo import structs

    def fake_init(self, server):
        self.server = server
        self.memory = SimpleNamespace()

    mocker.patch.object(Client, "__init__", fake_init)
    mocker.patch.object(Client, "_connect")
    mocker.patch.object(Client, "wait_for_packet", return_value=(structs.ServerIdType.JOIN_GAME, 0, bytes(ctypes.sizeof(structs.StocJoinGame))))
    mocker.patch("game.client.variables.config.get", return_value="Tester")

    sent = []

    def capture_send(self, packet_id, data=None):
        sent.append(packet_id)

    mocker.patch.object(Client, "send", capture_send)
    server = MagicMock()

    client = Client.join_room(server, 123, as_observer=True)

    assert client.room_id == 123
    assert client.memory.is_observer is True
    assert structs.ClientIdType.TO_OBSERVER in sent


def test_server_ui_spectate_room(mocker):
    from ui import server_ui

    mocker.patch("ui.server_ui.StatusMessage")
    mocker.patch("ui.server_ui.utils.output")
    joined_client = MagicMock()
    joined_client.memory = SimpleNamespace()
    mocker.patch("ui.server_ui.Client.join_room", return_value=joined_client)
    room = MagicMock()
    room.roomid = 55
    room.needpass = False
    server = MagicMock()
    server.get_room.return_value = room

    server_ui.spectate_room(server, 55)

    server_ui.Client.join_room.assert_called_with(server, 55, None, as_observer=True)
    assert joined_client.memory.is_observer is True
    server_ui.utils.output.assert_called_with("Joined room as spectator")


def test_room_menu_for_observer_has_no_deck_or_ready(mocker):
    from ui import room_ui
    from tests.test_ui_flows_more import FakeMenu

    mocker.patch("ui.room_ui.DynamicVerticalMenu", FakeMenu)
    mocker.patch("ui.room_ui.utils.get_ui_stack", return_value=MagicMock())
    mocker.patch("ui.room_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    mocker.patch("ui.room_ui.banlists.BanlistManager")
    room_ui.banlists.BanlistManager.return_value.get_banlist_by_hash.return_value.name = "No limits"

    client = MagicMock()
    client.memory = SimpleNamespace(is_host=False, is_observer=True, users_info=[])
    client.room.roomid = 1
    client.room.needpass = False
    client.room.roomnotes = ""
    client.room.banlist_hash = 0
    client.room.users = []

    menu = room_ui.display_room_menu.__wrapped__(client)
    labels = [item[0] for item in menu.items if isinstance(item[0], str)]

    assert "Spectating this room" in labels
    assert "Select/import Deck" not in labels
    assert "Ready" not in labels
