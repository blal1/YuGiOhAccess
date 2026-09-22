"""Things the README told players they could do, which the code did not do.

Each of these was advertised and missing: a key that nothing listened for, a
menu entry wired to nothing, a duel that stalled rather than asking again.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import wx


class FakeKeyEvent:
    def __init__(self, key, shift=False):
        self.key = key
        self.shift = shift

    def GetKeyCode(self):
        return self.key

    def ShiftDown(self):
        return self.shift

    def Skip(self):
        pass


def _bare_menu(mocker, cancel=None):
    """A BaseUI with no wx behind it, holding one row."""
    from ui.base_ui import BaseUI

    menu = BaseUI.__new__(BaseUI)
    menu.rows = 1
    menu.cols = 1
    menu.current_row = 0
    menu.current_col = 0
    menu.repeat_on_boundaries = False
    menu.cells = [[None]]
    menu.cell_functions = [[None]]
    menu.cell_extras = [[None]]
    menu.help_text = ""
    menu.cancel_action = cancel
    mocker.patch("ui.base_ui.utils.record_action")
    mocker.patch("ui.base_ui.utils.output")
    return menu


# ----------------------------------------------------- escape and backspace --

def test_escape_leaves_a_screen_that_has_a_way_out(mocker):
    went_back = MagicMock()
    menu = _bare_menu(mocker, cancel=went_back)
    mocker.patch("ui.base_ui.wx.Window.FindFocus", return_value=None)

    menu.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))

    went_back.assert_called_once()


def test_backspace_also_goes_back(mocker):
    went_back = MagicMock()
    menu = _bare_menu(mocker, cancel=went_back)
    mocker.patch("ui.base_ui.wx.Window.FindFocus", return_value=None)

    menu.on_key_down(FakeKeyEvent(wx.WXK_BACK))

    went_back.assert_called_once()


def test_backspace_still_deletes_text_when_typing(mocker):
    """The one place Backspace must not mean "go back"."""
    went_back = MagicMock()
    menu = _bare_menu(mocker, cancel=went_back)
    frame = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.Window.FindFocus", return_value=MagicMock(spec=wx.TextCtrl))

    menu.on_key_down(FakeKeyEvent(wx.WXK_BACK))

    went_back.assert_not_called()


def test_a_screen_with_no_way_out_passes_the_key_on(mocker):
    menu = _bare_menu(mocker, cancel=None)
    frame = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.Window.FindFocus", return_value=None)

    menu.on_key_down(FakeKeyEvent(wx.WXK_ESCAPE))

    frame.on_key_down.assert_called_once()


def test_a_back_item_binds_the_keys_to_itself(mocker):
    """Appending the Back entry is what registers Escape, in one step."""
    from ui.base_ui import BaseUI

    menu = BaseUI.__new__(BaseUI)
    menu.cancel_action = None
    menu.append_item = MagicMock(return_value="control")
    went_back = MagicMock()

    assert menu.append_cancel_item("Back", went_back) == "control"
    assert menu.cancel_action is went_back


def test_the_card_selection_prompt_can_really_be_cancelled(mocker):
    """It said "Press Escape to cancel selection" and nothing listened."""
    from ui.duel_messages import select_card

    menu = MagicMock()
    mocker.patch("ui.duel_messages.select_card.VerticalMenu", return_value=menu)
    mocker.patch("ui.duel_messages.select_card.SelectionLimiter")
    mocker.patch("ui.duel_messages.select_card.utils.get_ui_stack")
    mocker.patch("ui.duel_messages.select_card.utils.output")

    select_card.show_menu_with_presentable_cards(
        MagicMock(), [], ["a card"], 1, 1, False, cancelable=True
    )

    assert menu.append_cancel_item.called, "the Cancel entry does not bind Escape"


# --------------------------------------------------------------- retry ------

def test_a_rejected_answer_asks_the_question_again(mocker):
    """MSG_RETRY used to announce a failure and leave the duel stuck."""
    from game.edo.message_constants import MSG_SELECT_IDLECMD
    from ui.duel_messages import retry

    handler = MagicMock()
    mocker.patch.dict("core.utils.duel_message_handlers", {MSG_SELECT_IDLECMD: handler}, clear=False)
    call_after = mocker.patch("ui.duel_messages.retry.wx.CallAfter")
    mocker.patch("ui.duel_messages.retry.utils.output")

    prompt = (MSG_SELECT_IDLECMD, b"\x0b\x00", 2)
    client = SimpleNamespace(memory=SimpleNamespace(last_prompt=prompt))
    retry.msg_retry(client, b"\x01", 1)

    call_after.assert_called_once_with(handler, client, b"\x0b\x00", 2)


def test_a_retry_with_nothing_to_repeat_says_so(mocker):
    from ui.duel_messages import retry

    output = mocker.patch("ui.duel_messages.retry.utils.output")
    mocker.patch("ui.duel_messages.retry.wx.CallAfter")

    retry.msg_retry(SimpleNamespace(memory=SimpleNamespace()), b"\x01", 1)

    assert "could not be shown again" in output.call_args.args[0]


def test_only_prompts_meant_for_us_are_remembered(mocker):
    """A prompt addressed to the opponent is not ours to answer again."""
    import ui
    from game.edo.message_constants import MSG_SELECT_IDLECMD, MSG_NEW_PHASE

    client = SimpleNamespace(memory=SimpleNamespace(), what_player_am_i=0)

    ui.remember_prompt(client, MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 1]), 2)
    assert not hasattr(client.memory, "last_prompt")

    ui.remember_prompt(client, MSG_SELECT_IDLECMD, bytes([MSG_SELECT_IDLECMD, 0]), 2)
    assert client.memory.last_prompt[0] == MSG_SELECT_IDLECMD

    # Something that is not a question is not worth repeating either.
    ui.remember_prompt(client, MSG_NEW_PHASE, bytes([MSG_NEW_PHASE, 0]), 2)
    assert client.memory.last_prompt[0] == MSG_SELECT_IDLECMD


# ------------------------------------------------------------ small ones ----

def test_the_hand_can_be_shuffled_when_the_duel_offers_it(mocker):
    """can_shuffle was read off the wire and had nowhere to go."""
    from ui import duel_menu

    menu = MagicMock()
    mocker.patch("ui.duel_menu.VerticalMenu", return_value=menu)
    mocker.patch("ui.duel_menu.utils.get_ui_stack")
    client = MagicMock()
    client.is_it_my_turn = True
    client.current_phase = 4
    client.player.can_shuffle = 1

    duel_menu.show_duel_menu(client)

    labels = [call.args[0] for call in menu.append_item.call_args_list if call.args]
    assert any("Shuffle hand" in str(label) for label in labels)


def test_shuffling_the_hand_sends_the_command_the_core_expects(mocker):
    import struct

    from game.edo import structs
    from ui import duel_menu

    mocker.patch("ui.duel_menu.utils.get_ui_stack")
    client = MagicMock()

    duel_menu.send_shuffle_hand(client)

    client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("I", 8))


@pytest.mark.parametrize("missing", [None, "card", "target"])
def test_an_equip_names_both_cards_when_it_can(mocker, missing):
    """It used to say "Card equipped to target." and name neither."""
    from ui.duel_messages import equip

    output = mocker.patch("ui.duel_messages.equip.utils.output")
    card = None if missing == "card" else SimpleNamespace(get_name=lambda: "Equip Spell")
    target = None if missing == "target" else SimpleNamespace(get_name=lambda: "Blue-Eyes")

    equip.equip(MagicMock(), card, target)

    spoken = output.call_args.args[0]
    if missing != "card":
        assert "Equip Spell" in spoken
    if missing != "target":
        assert "Blue-Eyes" in spoken


def test_changing_your_nickname_is_reachable_from_the_main_menu(mocker):
    """The screen existed and nothing led to it."""
    from tests.test_ui_flows_more import FakeMenu
    from ui import main_ui

    mocker.patch("ui.main_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.main_ui.variables.DEV_OPTIONS", SimpleNamespace(server=None))
    mocker.patch("ui.main_ui.variables.IS_FROZEN", True)
    mocker.patch("ui.main_ui.variables.config", MagicMock(get=lambda key, default=None: "Tester"))
    mocker.patch("ui.main_ui.utils.get_discord_presence_manager")
    mocker.patch("ui.main_ui._apply_pending_catalog_refresh")
    mocker.patch("ui.main_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])

    menu = main_ui.main_menu_view.__wrapped__()

    labels = [str(item[0]) for item in menu.items]
    assert any("Change nickname" in label for label in labels)
    entry = next(item for item in menu.items if "Change nickname" in str(item[0]))
    assert callable(entry[1])
