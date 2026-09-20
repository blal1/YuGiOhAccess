import struct
from unittest.mock import MagicMock, patch, call

from game.edo import structs


def test_do_surrender_sends_packet(mocker):
    """Surrender sends SURRENDER packet and outputs message."""
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")

    from ui.duel_menu import do_surrender
    do_surrender(mock_client)

    mock_ui_stack.pop_ui.assert_called_once()
    mock_client.send.assert_called_once_with(structs.ClientIdType.SURRENDER)


def test_open_chat_input_sends_chat_packet(mocker):
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("core.utils.output")
    # The prompt is non blocking now: it hands the message back through a
    # callback instead of spinning wx.Yield() while the duel carries on.
    input_cls = mocker.patch("ui.duel_menu.CallbackInputUI")

    from ui.duel_menu import open_chat_input
    open_chat_input(mock_client)

    mock_ui_stack.pop_ui.assert_called_once()
    input_cls.return_value.show.assert_called_once()
    on_done = input_cls.call_args.args[1]
    on_done("hello")

    packet_id, packet = mock_client.send.call_args.args
    assert packet_id == structs.ClientIdType.CHAT
    assert bytes(packet)


def test_show_chat_history_outputs_recent_messages(mocker):
    mock_client = MagicMock()
    mock_client.memory.chat_history = [("Alice", "hello"), ("Bob", "hi")]
    mock_ui_stack = MagicMock()
    output = mocker.patch("core.utils.output")
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    from ui.duel_menu import show_chat_history
    show_chat_history(mock_client)

    mock_ui_stack.pop_ui.assert_called_once()
    assert output.call_args_list[0].args[0] == "Chat history:"
    assert output.call_args_list[-1].args[0] == "Bob: hi"


def test_show_chat_history_empty(mocker):
    mock_client = MagicMock()
    mock_client.memory = MagicMock()
    del mock_client.memory.chat_history
    mocker.patch("core.utils.get_ui_stack", return_value=MagicMock())
    output = mocker.patch("core.utils.output")

    from ui.duel_menu import show_chat_history
    show_chat_history(mock_client)

    output.assert_called_once_with("No chat messages yet.")


def test_read_chain_stack_and_menu_item(mocker):
    mock_client = MagicMock()
    mock_client.current_phase = 4
    mock_client.is_it_my_turn = True
    mock_client.player.lifepoints = 8000
    mock_client.player.opponent_lifepoints = 7000
    mock_client.player.turn_timer.get_remaining_time.return_value = 120
    mock_client.player.can_go_to_battle_phase = False
    mock_client.player.can_go_to_main_phase2 = False
    mock_client.player.can_go_to_end_phase = False
    mock_client.turn_count = 3
    mock_client.get_duel_field.return_value.get_chain_stack_text.return_value = "Current chain:\n1: Test"
    mock_ui_stack = MagicMock()
    output = mocker.patch("core.utils.output")
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    menu_cls = mocker.patch("ui.duel_menu.VerticalMenu")

    from ui.duel_menu import read_chain_stack, show_duel_menu
    read_chain_stack(mock_client)
    output.assert_called_once_with("Current chain:\n1: Test")

    show_duel_menu(mock_client)
    labels = [call.args[0] for call in menu_cls.return_value.append_item.call_args_list]
    assert "Read chain" in labels


def test_confirm_surrender_creates_menu(mocker):
    """Confirm surrender pops current UI and pushes new menu."""
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
    mocker.patch("ui.duel_menu.VerticalMenu")

    from ui.duel_menu import confirm_surrender
    confirm_surrender(mock_client)

    mock_ui_stack.pop_ui.assert_called_once()
    assert mock_ui_stack.push_ui.called


def test_send_battle_phase(mocker):
    mock_client = MagicMock()
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    from ui.duel_menu import send_battle_phase
    send_battle_phase(mock_client)

    mock_client.send.assert_called_once_with(
        structs.ClientIdType.RESPONSE, struct.pack('I', 6)
    )


def test_send_end_phase_main1(mocker):
    mock_client = MagicMock()
    mock_client.current_phase = 4  # main phase 1
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    from ui.duel_menu import send_end_phase
    send_end_phase(mock_client)

    mock_client.send.assert_called_once_with(
        structs.ClientIdType.RESPONSE, struct.pack('I', 7)
    )


def test_send_end_phase_battle(mocker):
    mock_client = MagicMock()
    mock_client.current_phase = 8  # battle phase
    mock_ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

    from ui.duel_menu import send_end_phase
    send_end_phase(mock_client)

    mock_client.send.assert_called_once_with(
        structs.ClientIdType.RESPONSE, struct.pack('I', 3)
    )


def test_cancelling_the_chat_prompt_sends_nothing(mocker):
    mock_client = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=MagicMock())
    mocker.patch("core.utils.output")
    input_cls = mocker.patch("ui.duel_menu.CallbackInputUI")

    from ui.duel_menu import open_chat_input
    open_chat_input(mock_client)
    input_cls.call_args.args[1](None)

    mock_client.send.assert_not_called()


def _frame_stub(stack):
    """Just enough frame for the UI stack logic in remove_ui."""
    from types import SimpleNamespace

    return SimpleNamespace(
        ui_stack=list(stack),
        main_sizer=MagicMock(),
        game_area=MagicMock(),
        Layout=MagicMock(),
        Fit=MagicMock(),
    )


def test_remove_ui_takes_a_screen_out_of_the_middle_of_the_stack():
    """A duel message can push a screen on top of an open prompt.

    Popping would then discard the duel screen and strand the prompt, which is
    what left the duel answering nothing but the menu bar.
    """
    from ui.frame import YuGiOhAccessFrame

    prompt, duel_screen, field = MagicMock(name="prompt"), MagicMock(name="duel"), MagicMock(name="field")
    frame = _frame_stub([field, prompt, duel_screen])

    assert YuGiOhAccessFrame.remove_ui(frame, prompt) is True

    assert frame.ui_stack == [field, duel_screen]
    # The screen on top was not touched, so the duel keeps the focus it had.
    duel_screen.SetFocus.assert_not_called()
    prompt.Destroy.assert_called_once()


def test_remove_ui_restores_the_screen_below_when_the_top_goes():
    from ui.frame import YuGiOhAccessFrame

    field, prompt = MagicMock(name="field"), MagicMock(name="prompt")
    frame = _frame_stub([field, prompt])

    assert YuGiOhAccessFrame.remove_ui(frame, prompt) is True

    assert frame.ui_stack == [field]
    field.Show.assert_called_once()
    field.SetFocus.assert_called_once()


def test_remove_ui_ignores_a_screen_that_is_not_on_the_stack():
    from ui.frame import YuGiOhAccessFrame

    frame = _frame_stub([MagicMock()])
    assert YuGiOhAccessFrame.remove_ui(frame, MagicMock()) is False
    assert len(frame.ui_stack) == 1


def test_remove_ui_survives_an_already_destroyed_screen():
    from ui.frame import YuGiOhAccessFrame

    prompt = MagicMock()
    prompt.Destroy.side_effect = RuntimeError("already deleted")
    frame = _frame_stub([MagicMock(), prompt])

    assert YuGiOhAccessFrame.remove_ui(frame, prompt) is True
    assert prompt not in frame.ui_stack
