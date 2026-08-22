import importlib
import struct
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

from tests.test_duel_messages_simple_more import NamedCard, _client
from tests.test_ui_flows_more import FakeMenu


def test_action_menu_single_activation_and_misc_small_ui_modules(mocker):
    from game.edo import structs
    from ui import action_menu, duel_state_change_ui
    from ui.tab_order import DuelFieldTabOrder

    client, stack = _client(mocker)
    mocker.patch("ui.action_menu.Card", NamedCard)
    mocker.patch("ui.action_menu.VerticalMenu", FakeMenu)
    card = NamedCard("Action")
    card.strings = ["unused"]
    card.data = 99
    card.get_effect_description = MagicMock(return_value="effect")
    client.player = SimpleNamespace(
        attackable=[],
        activatable=[card],
        special_summonable=[],
        summonable=[],
        monster_settable=[],
        spell_settable=[],
        repositionable=[],
    )
    zone = SimpleNamespace(card=card)
    action_menu.show_action_menu_for_zone(client, zone)
    menu = stack.push_ui.call_args.args[0]
    assert "Activate effect" in menu.items[1][0]
    menu.items[1][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 5))

    order = DuelFieldTabOrder()
    order.set_tabable_items(["a", "b"])
    order.current_index = -1
    assert order.resolve_previous_tab_order() == "b"

    mocker.patch("ui.duel_state_change_ui.match_ui.is_match", return_value=True)
    mocker.patch("ui.duel_state_change_ui.match_ui.score_text", return_value="score")
    presence = MagicMock()
    mocker.patch("ui.duel_state_change_ui.utils.get_discord_presence_manager", return_value=presence)
    duel_state_change_ui.handle_duel_start(client, b"", 0)
    presence.update_presence.assert_called()

    mocker.patch("ui.duel_state_change_ui.replay_ui.finish_replay_recording")
    mocker.patch("ui.duel_state_change_ui.match_ui.is_match_over", return_value=False)
    call_later = mocker.patch("ui.duel_state_change_ui.wx.CallLater")
    duel_state_change_ui.handle_duel_end(client, b"", 0)
    assert call_later.call_args.args[1] == stack.clear_ui_stack

    replay_file = SimpleNamespace(name="duel.yrp")
    save_replay = mocker.patch("ui.duel_state_change_ui.replay_ui.save_replay_packet", return_value=replay_file)
    duel_state_change_ui.handle_new_replay(client, b"abc", 3)
    duel_state_change_ui.handle_replay(client, b"def", 3)
    assert save_replay.call_count == 2


def test_last_duel_message_edges_and_output2_darwin(mocker):
    from game.card import card_constants
    from ui.duel_messages import become_target

    client, _stack = _client(mocker)

    class ChangingTruthCard(NamedCard):
        def __init__(self):
            super().__init__("Changing")
            self.calls = 0

        def __bool__(self):
            self.calls += 1
            return self.calls == 1

    card = ChangingTruthCard()
    client.get_card.return_value = card
    become_target.become_target(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK)

    sys.modules.pop("ui.output2", None)
    popen = mocker.patch("subprocess.Popen")
    mocker.patch("platform.system", return_value="Darwin")
    output2 = importlib.import_module("ui.output2")
    assert isinstance(output2.output, output2.OsaScriptSingleton)
    output2.output.output("hello")
    popen.return_value.stdin.write.assert_called()

    sys.modules.pop("ui.output2", None)
    auto = MagicMock()
    mocker.patch("platform.system", return_value="Windows")
    mocker.patch.dict(sys.modules, {"accessible_output3.outputs.auto": SimpleNamespace(Auto=MagicMock(return_value=auto))})
    output2 = importlib.import_module("ui.output2")
    assert output2.output is not None
