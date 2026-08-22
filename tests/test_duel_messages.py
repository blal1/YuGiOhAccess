"""Tests for new duel message handlers: retry, shuffle_hand, damage, sort_card, select_counter, select_sum, confirm_decktop, player_hint."""
import io
import struct
from unittest.mock import MagicMock, patch, call


def _make_client_mock(mocker, player_id=0):
    """Create a mock client with read helpers from real Client."""
    from game.client import Client
    mock_server = MagicMock()
    mocker.patch.object(Client, "__init__", lambda self, *a, **kw: None)
    client = Client.__new__(Client)
    client.what_player_am_i = player_id
    client.game_socket = MagicMock()
    client.send = MagicMock()

    def read_u8(buf):
        return struct.unpack('B', buf.read(1))[0]
    def read_u16(buf):
        return struct.unpack('<H', buf.read(2))[0]
    def read_u32(buf):
        return struct.unpack('<I', buf.read(4))[0]
    def read_u64(buf):
        return struct.unpack('<Q', buf.read(8))[0]
    def read_location(buf):
        controller = struct.unpack('B', buf.read(1))[0]
        location = struct.unpack('B', buf.read(1))[0]
        sequence = struct.unpack('<I', buf.read(4))[0]
        position = struct.unpack('<I', buf.read(4))[0]
        return controller, location, sequence, position

    client.read_u8 = read_u8
    client.read_u16 = read_u16
    client.read_u32 = read_u32
    client.read_u64 = read_u64
    client.read_location = read_location
    return client


class TestMsgRetry:
    def test_retry_outputs_message(self, mocker):
        mocker.patch("core.utils.output")
        from ui.duel_messages.retry import msg_retry
        client = MagicMock()
        msg_retry(client, b'\x01', 1)
        from core.utils import output
        output.assert_called_once()


class TestMsgShuffleHand:
    def test_shuffle_own_hand(self, mocker):
        mocker.patch("core.utils.output")
        client = MagicMock()
        client.what_player_am_i = 0
        client.read_u8 = lambda buf: struct.unpack('B', buf.read(1))[0]
        client.read_u32 = lambda buf: struct.unpack('<I', buf.read(4))[0]
        data = b'\x08' + struct.pack('B', 0) + struct.pack('<I', 2) + struct.pack('<I', 12345) + struct.pack('<I', 67890)
        from ui.duel_messages.shuffle_hand import msg_shuffle_hand
        msg_shuffle_hand(client, data, len(data))
        from core import utils
        assert utils.output.called
        assert any("hand" in str(c).lower() for c in utils.output.call_args_list)

    def test_shuffle_opponent_hand(self, mocker):
        mocker.patch("core.utils.output")
        client = MagicMock()
        client.what_player_am_i = 0
        client.read_u8 = lambda buf: struct.unpack('B', buf.read(1))[0]
        client.read_u32 = lambda buf: struct.unpack('<I', buf.read(4))[0]
        data = b'\x08' + struct.pack('B', 1) + struct.pack('<I', 2) + struct.pack('<I', 12345) + struct.pack('<I', 67890)
        from ui.duel_messages.shuffle_hand import msg_shuffle_hand
        msg_shuffle_hand(client, data, len(data))
        from core import utils
        assert utils.output.called
        assert any("opponent" in str(c).lower() for c in utils.output.call_args_list)

    def test_shuffle_extra(self, mocker):
        mocker.patch("core.utils.output")
        client = MagicMock()
        client.what_player_am_i = 0
        client.read_u8 = lambda buf: struct.unpack('B', buf.read(1))[0]
        client.read_u32 = lambda buf: struct.unpack('<I', buf.read(4))[0]
        data = b'\x09' + struct.pack('B', 0) + struct.pack('<I', 3)
        from ui.duel_messages.shuffle_hand import msg_shuffle_extra
        msg_shuffle_extra(client, data, len(data))
        from core import utils
        assert utils.output.called
        assert any("extra" in str(c).lower() for c in utils.output.call_args_list)


class TestMsgDamage:
    def test_damage_to_self(self, mocker):
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        client = _make_client_mock(mocker, player_id=0)
        data = b'\x5f' + struct.pack('B', 0) + struct.pack('<I', 500)
        from ui.duel_messages.damage import msg_damage
        msg_damage(client, data, len(data))
        from core.utils import output
        assert any("500" in str(c) for c in output.call_args_list)

    def test_damage_to_opponent(self, mocker):
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        client = _make_client_mock(mocker, player_id=0)
        data = b'\x5f' + struct.pack('B', 1) + struct.pack('<I', 1000)
        from ui.duel_messages.damage import msg_damage
        msg_damage(client, data, len(data))
        from core.utils import output
        assert any("opponent" in str(c) for c in output.call_args_list)


class TestMsgSortCard:
    def test_finish_sort_packs_order(self, mocker):
        mock_client = MagicMock()
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        from ui.duel_messages.sort_card import finish_sort
        from game.edo import structs
        order = [2, 0, 1]
        finish_sort(mock_client, order)
        expected = struct.pack('I', 1) + struct.pack('B', 2) + struct.pack('B', 0) + struct.pack('B', 1)
        mock_client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, expected)


class TestMsgSelectCounter:
    def test_finish_counter_selection_valid(self, mocker):
        import wx
        mock_client = MagicMock()
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")

        mock_menu = MagicMock()
        slider1 = MagicMock(spec=wx.Slider)
        slider1.GetValue.return_value = 2
        slider2 = MagicMock(spec=wx.Slider)
        slider2.GetValue.return_value = 1
        mock_menu.cells = [[slider1], [slider2]]

        cards = [MagicMock(), MagicMock()]

        from ui.duel_messages.select_counter import finish_counter_selection
        from game.edo import structs
        finish_counter_selection(mock_client, mock_menu, cards, 3)

        expected = struct.pack('I', 1) + struct.pack('H', 2) + struct.pack('H', 1)
        mock_client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, expected)

    def test_finish_counter_selection_invalid_sum(self, mocker):
        import wx
        mock_client = MagicMock()
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")

        mock_menu = MagicMock()
        slider1 = MagicMock(spec=wx.Slider)
        slider1.GetValue.return_value = 1
        mock_menu.cells = [[slider1]]

        cards = [MagicMock()]

        from ui.duel_messages.select_counter import finish_counter_selection
        finish_counter_selection(mock_client, mock_menu, cards, 3)

        # Should not send, just output error
        mock_client.send.assert_not_called()
        from core.utils import output
        output.assert_called()


class TestMsgSelectSum:
    def test_finish_sum_exact_mode_valid(self, mocker):
        import wx
        mock_client = MagicMock()
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")

        mock_menu = MagicMock()
        cb1 = MagicMock(spec=wx.CheckBox)
        cb1.IsChecked.return_value = True
        cb2 = MagicMock(spec=wx.CheckBox)
        cb2.IsChecked.return_value = False
        mock_menu.cells = [[cb1], [cb2]]

        must_select = [MagicMock(param=0x0004)]  # level 4
        can_select = [MagicMock(param=0x0004), MagicMock(param=0x0003)]  # level 4, 3
        target_sum = 8  # 4 (must) + 4 (selected) = 8

        from ui.duel_messages.select_sum import finish_sum_selection
        from game.edo import structs
        finish_sum_selection(mock_client, mock_menu, must_select, can_select, target_sum, 0)

        expected = struct.pack('I', 1) + struct.pack('I', 2) + struct.pack('H', 0) + struct.pack('H', 1)
        mock_client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, expected)

    def test_finish_sum_exact_mode_invalid(self, mocker):
        import wx
        mock_client = MagicMock()
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")

        mock_menu = MagicMock()
        cb1 = MagicMock(spec=wx.CheckBox)
        cb1.IsChecked.return_value = True
        mock_menu.cells = [[cb1]]

        must_select = [MagicMock(param=0x0004)]  # level 4
        can_select = [MagicMock(param=0x0003)]  # level 3
        target_sum = 10  # 4 + 3 = 7 != 10

        from ui.duel_messages.select_sum import finish_sum_selection
        finish_sum_selection(mock_client, mock_menu, must_select, can_select, target_sum, 0)

        mock_client.send.assert_not_called()
        from core.utils import output
        output.assert_called()
