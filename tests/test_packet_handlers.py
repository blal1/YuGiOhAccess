"""Test that all packet handlers and duel message handlers are registered."""
from unittest.mock import MagicMock


def test_duel_message_handlers_registered(mocker):
    """Every duel message ocgcore defines has a handler.

    The ids come from game.edo.message_constants, which is generated from
    ocgcore's ocgapi_constants.h. Listing them by hand here is what let three
    different, contradictory id tables live in this repo.
    """
    import ui  # noqa: F401
    from core import utils
    from game.edo import message_constants

    registered = {int(msg_id) for msg_id in utils.duel_message_handlers if msg_id != -1}
    missing = sorted(message_constants.ALL_MESSAGE_IDS - registered)
    assert missing == [], [message_constants.MESSAGE_NAMES[i] for i in missing]


def test_no_handler_is_registered_on_an_undefined_id(mocker):
    """A handler on an id the core does not define never runs, or worse, steals
    another message's buffer and raises struct.error."""
    import ui  # noqa: F401
    from core import utils
    from game.edo import message_constants

    registered = {int(msg_id) for msg_id in utils.duel_message_handlers if msg_id != -1}
    unknown = sorted(registered - message_constants.ALL_MESSAGE_IDS)
    assert unknown == []


def test_handlers_are_registered_on_the_id_their_name_says(mocker):
    """Spot check the ids that used to be wrong across the three tables."""
    import ui  # noqa: F401
    from core import utils
    from game.edo import message_constants as mc

    expected = {
        mc.MSG_SELECT_COUNTER: "msg_select_counter",
        mc.MSG_SELECT_SUM: "msg_select_sum",
        mc.MSG_SORT_CARD: "msg_sort_card",
        mc.MSG_SORT_CHAIN: "msg_sort_chain",
        mc.MSG_SELECT_UNSELECT_CARD: "msg_select_unselect_card",
        mc.MSG_CONFIRM_DECKTOP: "msg_confirm_decktop",
        mc.MSG_CONFIRM_CARDS: "msg_confirm_cards",
        mc.MSG_SHUFFLE_HAND: "msg_shuffle_hand",
        mc.MSG_SHUFFLE_SET_CARD: "msg_shuffle_set_card",
        mc.MSG_SWAP_GRAVE_DECK: "msg_swap_grave_deck",
        mc.MSG_PLAYER_HINT: "msg_player_hint",
        mc.MSG_RELOAD_FIELD: "msg_reload_field",
        mc.MSG_DAMAGE: "msg_damage",
    }
    for msg_id, name in expected.items():
        handler = utils.duel_message_handlers.get(msg_id)
        assert handler is not None, f"no handler for {msg_id}"
        assert handler.__name__ == name, f"{msg_id} is handled by {handler.__name__}, expected {name}"


def test_packet_handlers_registered(mocker):
    """Key server packet handlers are registered."""
    import ui  # noqa: F401
    from core import utils
    from game.edo import structs

    required_handlers = [
        structs.ServerIdType.CHAT_2,
        structs.ServerIdType.ERROR_MSG,
        structs.ServerIdType.GAME_MSG,
        structs.ServerIdType.CHANGE_SIDE,
        structs.ServerIdType.ORDER_RESULT,
        structs.ServerIdType.WAITING_SIDE,
        structs.ServerIdType.NEW_REPLAY,
        structs.ServerIdType.REPLAY,
        structs.ServerIdType.LEAVE_GAME,
    ]
    for packet_id in required_handlers:
        assert packet_id in utils.packet_handlers, f"Missing handler for packet {packet_id}"


def test_handle_change_side_calls_side_deck_ui(mocker):
    """CHANGE_SIDE handler invokes side deck UI."""
    mock_show = mocker.patch("ui.side_deck_ui.show_side_deck_ui")
    from ui import handle_change_side
    client = MagicMock()
    handle_change_side(client, b'', 0)
    mock_show.assert_called_once_with(client)


def test_handle_waiting_side_outputs(mocker):
    mocker.patch("core.utils.output")
    from ui import handle_waiting_side
    handle_waiting_side(MagicMock(), b'', 0)
    from core.utils import output
    output.assert_called_once()


def test_handle_leave_game_outputs(mocker):
    mocker.patch("core.utils.output")
    from ui import handle_leave_game
    handle_leave_game(MagicMock(), b'', 0)
    from core.utils import output
    output.assert_called_once()


def test_handle_order_result_outputs_turn_order(mocker):
    from types import SimpleNamespace
    from ui.rock_paper_scissors_ui import handle_order_result

    output = mocker.patch("core.utils.output")
    client = SimpleNamespace(what_player_am_i=0)

    handle_order_result(client, b"\x00", 1)
    handle_order_result(client, b"\x01", 1)
    handle_order_result(client, b"", 0)

    assert output.call_args_list[0].args[0] == "You will go first."
    assert output.call_args_list[1].args[0] == "Your opponent will go first."


def test_handle_chat_2_stores_history(mocker):
    from types import SimpleNamespace
    from game.edo import structs, structs_utils
    from ui import handle_chat_2

    output = mocker.patch("core.utils.output")
    client = SimpleNamespace(memory=SimpleNamespace())
    packet = structs.StocChat2()
    packet.client_name = structs_utils.string_to_u16("Alice", 20)
    packet.msg = structs_utils.string_to_u16("Hello", 256)

    handle_chat_2(client, bytes(packet), len(bytes(packet)))

    assert client.memory.chat_history == [("Alice", "Hello")]
    output.assert_called_once_with("Alice: Hello")


def test_handle_chat_2_accepts_local_server_compact_packet(mocker):
    from types import SimpleNamespace
    from server.protocol import encode_string_utf16
    from ui import handle_chat_2

    output = mocker.patch("core.utils.output")
    client = SimpleNamespace(memory=SimpleNamespace())
    packet = b"\x01\x00" + encode_string_utf16("Bot ready", 256)

    handle_chat_2(client, packet, len(packet))

    assert client.memory.chat_history == [("Player 2", "Bot ready")]
    output.assert_called_once_with("Player 2: Bot ready")


def test_handle_chat_2_ignores_malformed_packet(mocker):
    from types import SimpleNamespace
    from ui import handle_chat_2

    output = mocker.patch("core.utils.output")
    client = SimpleNamespace(memory=SimpleNamespace())

    handle_chat_2(client, b"\x01", 1)

    assert not hasattr(client.memory, "chat_history")
    output.assert_not_called()
