import json
import socket
from pathlib import Path
import requests
from game.serverinfo import EdoServerInformation

def test_server_init():
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    assert server.name == "test server"
    assert server.address == "localhost"
    assert server.room_listing_port == 1111
    assert server.lobby_port == 2222
    assert server.room_session is not None

def test_server_is_available_success(mocker):
    mocker.patch("requests.Session.head").return_value = True
    mocker.patch("socket.create_connection").return_value = socket.socket()
    mocker.patch("game.serverinfo.EdoServerInformation.resolve_hostname_to_ip", return_value="1.1.1.1")
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    assert server.is_available("unknown")

def test_server_is_available_failure_fail_http(mocker):
    mocker.patch("requests.Session.head").side_effect = requests.exceptions.RequestException
    mocker.patch("socket.create_connection").return_value = socket.socket()
    mocker.patch("game.serverinfo.EdoServerInformation.resolve_hostname_to_ip", return_value="1.1.1.1")
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    assert not server.is_available("unknown")

def test_server_is_available_failure_fail_socket(mocker):
    mocker.patch("requests.Session.head").return_value = True
    mocker.patch("socket.create_connection").return_value = None
    mocker.patch("game.serverinfo.EdoServerInformation.resolve_hostname_to_ip", return_value="1.1.1.1")
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    assert not server.is_available("unknown")

def test_server_is_available_failure_timeout(mocker):
    mocker.patch("requests.Session.head").return_value = True
    mocker.patch("socket.create_connection").side_effect = socket.timeout
    mocker.patch("game.serverinfo.EdoServerInformation.resolve_hostname_to_ip", return_value="1.1.1.1")
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    assert not server.is_available("unknown")

room_data_file = Path(__file__).parent / "data/server_rooms.json"
rooms_json = room_data_file.read_text(encoding="utf-8")
rooms_json = json.loads(rooms_json)["rooms"]

def test_server_get_room(mocker):
    mocker.patch("game.serverinfo.EdoServerInformation._get_room_json", return_value=rooms_json)
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    room = server.get_room(1)
    assert room.roomid == 1  

def test_server_list_rooms(mocker):
    mocker.patch("game.serverinfo.EdoServerInformation._get_room_json", return_value=rooms_json)
    server = EdoServerInformation("test server", "localhost", 1111, 2222)
    rooms = server.list_rooms()
    assert len(rooms) == 4
    assert rooms[0].roomid == 1
    assert rooms[1].roomid == 2
