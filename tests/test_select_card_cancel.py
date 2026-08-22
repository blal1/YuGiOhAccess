import struct
from unittest.mock import MagicMock

from game.edo import structs


def test_cancel_card_selection_sends_ffffffff(mocker):
    """Cancel selection sends 0xFFFFFFFF response."""
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    from ui.duel_messages.select_card import cancel_card_selection
    cancel_card_selection(mock_client)

    mock_ui_stack.pop_ui.assert_called_once()
    mock_client.send.assert_called_once_with(
        structs.ClientIdType.RESPONSE, struct.pack('I', 0xFFFFFFFF)
    )


def test_finish_card_selection_packs_response(mocker):
    """finish_card_selection packs selected indices correctly."""
    import wx
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    mock_menu = MagicMock()
    cb1 = MagicMock(spec=wx.CheckBox)
    cb1.IsChecked.return_value = True
    cb2 = MagicMock(spec=wx.CheckBox)
    cb2.IsChecked.return_value = False
    cb3 = MagicMock(spec=wx.CheckBox)
    cb3.IsChecked.return_value = True
    mock_menu.cells = [[cb1], [cb2], [cb3]]

    cards = [MagicMock(), MagicMock(), MagicMock()]

    from ui.duel_messages.select_card import finish_card_selection
    finish_card_selection(mock_client, mock_menu, cards, 1, 3, False)

    expected_buf = struct.pack('I', 1)
    expected_buf += struct.pack('I', 2)  # 2 selected
    expected_buf += struct.pack('H', 0)  # index 0
    expected_buf += struct.pack('H', 2)  # index 2
    mock_client.send.assert_called_once_with(
        structs.ClientIdType.RESPONSE, expected_buf
    )
