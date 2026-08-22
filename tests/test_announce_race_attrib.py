import struct
from unittest.mock import MagicMock


def _client():
    client = MagicMock()
    client.read_u8 = lambda buf: struct.unpack("B", buf.read(1))[0]
    client.read_u32 = lambda buf: struct.unpack("<I", buf.read(4))[0]
    return client


def test_announce_attribute_single_choice_sends_bitmask(mocker):
    mock_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_stack)
    mock_menu = MagicMock()
    mocker.patch("ui.duel_messages.announce_attrib.VerticalMenu", return_value=mock_menu)
    mock_lang = MagicMock()
    mock_lang.strings = {"system": {1010: "Earth", 1011: "Water"}}
    mocker.patch("ui.duel_messages.announce_attrib.variables.LANGUAGE_HANDLER", mock_lang)

    from game.edo import structs
    from ui.duel_messages.announce_attrib import announce_attrib

    client = _client()
    announce_attrib(client, 0, 1, 0b11)

    assert mock_menu.append_item.call_count == 2
    mock_stack.push_ui.assert_called_once_with(mock_menu)
    first_callback = mock_menu.append_item.call_args_list[0].kwargs["function"]
    first_callback()
    client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1))


def test_announce_race_multi_choice_requires_exact_count(mocker):
    mock_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_stack)
    mock_menu = MagicMock()
    mocker.patch("ui.duel_messages.announce_attrib.VerticalMenu", return_value=mock_menu)
    mocker.patch("core.utils.output")
    mock_lang = MagicMock()
    mock_lang.strings = {"system": {1020: "Warrior", 1021: "Spellcaster"}}
    mocker.patch("ui.duel_messages.announce_attrib.variables.LANGUAGE_HANDLER", mock_lang)

    from game.edo import structs
    from ui.duel_messages.announce_race import announce_race

    client = _client()
    announce_race(client, 0, 2, 0b11)

    callbacks = [call.kwargs.get("function") for call in mock_menu.append_item.call_args_list]
    callbacks = [callback for callback in callbacks if callback]
    callbacks[0]()
    client.send.assert_not_called()
    callbacks[1]()
    client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("I", 3))


def test_msg_announce_attribute_parses_packet(mocker):
    mock_announce = mocker.patch("ui.duel_messages.announce_attrib.announce_attrib")
    from ui.duel_messages.announce_attrib import msg_announce_attrib

    client = _client()
    data = b"\x8d" + struct.pack("<BBI", 1, 2, 0x15)
    msg_announce_attrib(client, data, len(data))

    mock_announce.assert_called_once_with(client, 1, 2, 0x15)


def test_msg_announce_race_parses_packet(mocker):
    mock_announce = mocker.patch("ui.duel_messages.announce_race.announce_race")
    from ui.duel_messages.announce_race import msg_announce_race

    client = _client()
    data = b"\x8c" + struct.pack("<BBI", 0, 1, 0x04)
    msg_announce_race(client, data, len(data))

    mock_announce.assert_called_once_with(client, 0, 1, 0x04)
