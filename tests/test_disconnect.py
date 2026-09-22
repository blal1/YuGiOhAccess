"""Test client disconnect detection."""
from unittest.mock import MagicMock


def test_handle_disconnect_outputs_message(mocker):
    """_handle_disconnect announces disconnection and returns to main menu."""
    mocker.patch("core.utils.output")
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mock_main_menu = MagicMock()
    mocker.patch("core.utils.get_main_menu_function", return_value=mock_main_menu)

    from game.client import Client
    mocker.patch.object(Client, "__init__", lambda self, *a, **kw: None)
    client = Client.__new__(Client)
    client._handle_disconnect()

    from core.utils import output
    output.assert_called_once()
    mock_ui_stack.clear_ui_stack.assert_called_once()
    mock_main_menu.assert_called_once()


def test_handle_disconnect_no_main_menu(mocker):
    """_handle_disconnect gracefully handles missing main menu function."""
    mocker.patch("core.utils.output")
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.get_main_menu_function", return_value=None)

    from game.client import Client
    mocker.patch.object(Client, "__init__", lambda self, *a, **kw: None)
    client = Client.__new__(Client)
    client._handle_disconnect()

    mock_ui_stack.clear_ui_stack.assert_called_once()
