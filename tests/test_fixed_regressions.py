"""Regressions for bugs that were found by reading the code.

Each test here pins down one specific way the client used to misbehave. They
are grouped in one file on purpose: every one of them is a case an existing
test walked straight past, so keeping them together makes the gap visible.
"""

import struct
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import wx


# --------------------------------------------------------------------------
# The card list used to hang on the first card
# --------------------------------------------------------------------------

class _ListCard:
    def __init__(self, name="Card"):
        self.name = name

    def get_name(self):
        return self.name

    def __str__(self):
        return f"Details for {self.name}"


def _card_list(mocker):
    from ui import card_list_ui

    mocker.patch("ui.card_list_ui.Card", _ListCard)
    mocker.patch("ui.card_list_ui.HorizontalMenu.__init__", return_value=None)
    mocker.patch("ui.card_list_ui.HorizontalMenu.append_item")
    mocker.patch("ui.card_list_ui.HorizontalCardList.Bind")
    mocker.patch("ui.card_list_ui.utils.output")
    mocker.patch("ui.card_list_ui.utils.get_ui_stack", return_value=MagicMock())

    field = MagicMock()
    field.resolve_labels_for_card.return_value = "Label"
    field.get_card_accessibility_details.return_value = []
    client = MagicMock()
    client.get_duel_field.return_value = field

    card_list = card_list_ui.HorizontalCardList(client, "Cards", [_ListCard("A"), _ListCard("B")])
    card_list.return_value = None
    return card_list


def test_selecting_the_first_card_returns_instead_of_hanging(mocker):
    """Index 0 is an answer, not "nothing chosen yet".

    ``select_card`` waited on the truthiness of the answer, so picking the top
    card of a graveyard, banished pile or extra deck spun forever.
    """
    card_list = _card_list(mocker)
    yields = mocker.patch(
        "ui.card_list_ui.wx.Yield",
        side_effect=lambda: card_list.set_return_value(0),
    )

    assert card_list.select_card() == 0
    assert yields.call_count == 1


def test_cancelling_the_card_list_still_returns_minus_one(mocker):
    card_list = _card_list(mocker)
    mocker.patch("ui.card_list_ui.wx.Yield", side_effect=lambda: card_list.set_return_value(-1))

    assert card_list.select_card() == -1


# --------------------------------------------------------------------------
# Chaining with a card the duel did not offer
# --------------------------------------------------------------------------

class _ChainCard:
    def __init__(self, code=1, chain_index=3):
        self.code = code
        self.name = f"Card {code}"
        self.chain_index = chain_index

    def get_name(self):
        return self.name

    def __eq__(self, other):
        return getattr(other, "code", None) == self.code


def _chain_field(mocker, chaining_cards):
    from ui.duel_field import DuelField

    mocker.patch("ui.duel_field.Card", _ChainCard)
    mocker.patch("ui.duel_field.utils.output")
    field = DuelField.__new__(DuelField)
    field.tab_order = MagicMock()
    field._preemtive_key_handler = "something"
    field.client = MagicMock()
    field.client.player.chaining_cards = chaining_cards
    return field


def test_chaining_answers_with_the_card_that_matches_not_the_first_one(mocker):
    """The match decides the answer, not the position in the list.

    The loop returned on its first pass, so only the first offered card was
    ever compared and only its chain index could ever be sent.
    """
    from game.edo import structs
    from ui.duel_field import Zone

    wanted = _ChainCard(code=2, chain_index=9)
    field = _chain_field(mocker, [_ChainCard(code=1, chain_index=4), wanted])

    assert field.resolve_chain(Zone("z", wanted)) is True
    field.client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("I", 9))
    assert field.preemtive_key_handler is None


def test_chaining_with_an_unoffered_card_says_so_and_sends_nothing(mocker):
    from ui import duel_field
    from ui.duel_field import Zone

    field = _chain_field(mocker, [_ChainCard(code=1)])

    assert field.resolve_chain(Zone("z", _ChainCard(code=99))) is True
    field.client.send.assert_not_called()
    spoken = duel_field.utils.output.call_args.args[0]
    assert "cannot be chained" in spoken


def test_no_chain_prompt_leaves_the_key_to_the_normal_handler(mocker):
    from ui.duel_field import Zone

    field = _chain_field(mocker, [])

    assert field.resolve_chain(Zone("z", _ChainCard(code=1))) is False
    field.client.send.assert_not_called()


# --------------------------------------------------------------------------
# A player can be asked about attackers before the first prompt arrives
# --------------------------------------------------------------------------

def test_the_turn_clock_does_not_hold_the_process_open(mocker):
    """The duel clock is a daemon, and stopping it actually returns.

    As a normal thread it kept the interpreter alive for the rest of the turn
    after the window closed, and ``stop()`` joined the counting thread while
    holding the lock that thread needs on every tick.
    """
    from game.player import CountdownTimer

    mocker.patch("game.player.utils.get_ui_stack", return_value=MagicMock())
    timer = CountdownTimer(2)
    try:
        assert timer.thread.daemon is True
        timer.stop()
        assert timer.thread.is_alive() is False
    finally:
        timer.running = False


def test_attackable_is_readable_before_the_first_prompt(mocker):
    """Walking the field between MSG_START and the first prompt used to raise.

    ``_attackable`` existed only once ``clear_all()`` had run, and reading any
    zone asks the player whether the card in it can attack.
    """
    from game import player as player_module

    mocker.patch.object(player_module.Player, "handle_potential_music_change")
    mocker.patch.object(player_module, "CountdownTimer", MagicMock())

    player = player_module.Player(8000, 8000)

    assert player.attackable == []
    player.clear_all()
    assert player.attackable == []


# --------------------------------------------------------------------------
# A battle against player 0's first monster is still a battle
# --------------------------------------------------------------------------

class _BattleCard:
    def __init__(self, name, link=False):
        from game.card import card_constants

        self.name = name
        self.type = card_constants.TYPE.LINK if link else card_constants.TYPE.MONSTER

    def get_name(self):
        return self.name


def test_battle_against_the_first_zone_of_player_zero_names_the_defender(mocker):
    """An all zero reference means "no target"; a single zero does not.

    Testing the fields one at a time with ``and`` reported a battle against
    player 0's monster in the first zone as an attack into thin air.
    """
    from ui.duel_messages import damage_step_battle

    mocker.patch("ui.duel_messages.damage_step_battle.utils.output")
    client = MagicMock()
    client.get_card.side_effect = [_BattleCard("Attacker"), _BattleCard("Defender")]

    damage_step_battle.damage_step_battle(
        client,
        1, 0x04, 0, 0x1, 2000, 1000, 0,
        # controller 0, location monster zone, sequence 0, face up attack
        0, 0x04, 0, 0x1, 1500, 1200, 0,
    )

    spoken = damage_step_battle.utils.output.call_args.args[0]
    assert "Attacker (2000/1000) attacks Defender (1500/1200)" == spoken


def test_direct_attack_is_still_reported_without_a_defender(mocker):
    from ui.duel_messages import damage_step_battle

    mocker.patch("ui.duel_messages.damage_step_battle.utils.output")
    client = MagicMock()
    client.get_card.return_value = _BattleCard("Attacker")

    damage_step_battle.damage_step_battle(
        client,
        0, 0x04, 0, 0x1, 2000, 1000, 0,
        0, 0, 0, 0, 0, 0, 0,
    )

    spoken = damage_step_battle.utils.output.call_args.args[0]
    assert spoken == "Attacker (2000/1000) attacks"


def test_a_battle_survives_a_card_the_client_cannot_resolve(mocker):
    """get_card returns None for a zone we were never told about."""
    from ui.duel_messages import damage_step_battle

    mocker.patch("ui.duel_messages.damage_step_battle.utils.output")
    client = MagicMock()
    client.get_card.return_value = None

    damage_step_battle.damage_step_battle(
        client,
        0, 0x04, 0, 0x1, 2000, 1000, 0,
        0, 0, 0, 0, 0, 0, 0,
    )

    assert "2000/1000" in damage_step_battle.utils.output.call_args.args[0]


# --------------------------------------------------------------------------
# Config, language handler, client and frame
# --------------------------------------------------------------------------

def test_setting_a_preference_before_loading_does_not_raise():
    """A set() before the first load() has nowhere to save to."""
    from core.config import Config

    config = Config({"nickname": "Player"})
    config.set("nickname", "Tester")

    assert config.get("nickname") == "Tester"


def test_two_language_handlers_do_not_share_their_languages(mocker):
    from game.language_handler import LanguageHandler

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", "data")
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", "appdata")

    first = LanguageHandler()
    second = LanguageHandler()
    first.languages["english"] = {"short": "en"}
    first.primary_language = "english"

    assert second.languages == {}
    assert second.primary_language == ""


def test_disconnecting_before_connecting_is_not_an_error(mocker):
    from game.client import Client

    client = Client.__new__(Client)
    client.game_socket = None

    client.disconnect()  # must not raise


def test_refresh_rebuilds_the_screen_it_is_looking_at(mocker):
    """refresh_ui() with no argument rebuilds the current screen.

    It used to be impossible to call: utils passed no builder and the frame
    required one.
    """
    from core import utils
    from ui.frame import YuGiOhAccessFrame

    frame = YuGiOhAccessFrame.__new__(YuGiOhAccessFrame)
    rebuild = MagicMock()
    frame.ui_stack = [SimpleNamespace(rebuild=rebuild)]
    frame.prettify_ui_stack = MagicMock(return_value="[]")
    frame.pop_ui = MagicMock()

    mocker.patch("core.utils.wx.GetTopLevelWindows", return_value=[frame])
    utils.refresh_ui()

    rebuild.assert_called_once_with()
    # The builder replaces the screen itself; popping as well used to throw
    # away the screen underneath too.
    frame.pop_ui.assert_not_called()


def test_refreshing_a_screen_that_cannot_rebuild_is_harmless(mocker):
    from ui.frame import YuGiOhAccessFrame

    frame = YuGiOhAccessFrame.__new__(YuGiOhAccessFrame)
    frame.ui_stack = []
    frame.prettify_ui_stack = MagicMock(return_value="[]")
    frame.pop_ui = MagicMock()

    frame.refresh_ui()

    frame.pop_ui.assert_not_called()


def test_a_screen_remembers_how_it_was_built(mocker):
    """ui_function records a rebuild on the screen it pushes."""
    from core import utils

    frame = MagicMock()
    frame.ui_stack = []
    mocker.patch("core.utils.wx.GetTopLevelWindows", return_value=[frame])

    built = []

    @utils.ui_function
    def make_screen(title):
        screen = SimpleNamespace(title=title)
        built.append(screen)
        return screen

    make_screen("Room Menu")
    screen = frame.push_ui.call_args.args[0]

    assert callable(screen.rebuild)
    screen.rebuild()
    assert [item.title for item in built] == ["Room Menu", "Room Menu"]


# --------------------------------------------------------------------------
# Updates are checked on a fresh install too
# --------------------------------------------------------------------------

def test_a_fresh_install_still_checks_for_updates(mocker, tmp_path):
    from core import utils

    mocker.patch("core.utils.setup_logging")
    run_velopack = mocker.patch("core.utils.run_velopack")
    mocker.patch("core.utils.variables.APP_DATA_DIR", tmp_path / "brand-new")

    utils.setup()

    assert (tmp_path / "brand-new").exists()
    run_velopack.assert_called_once()


# --------------------------------------------------------------------------
# The extra deck survives a WindBot deck
# --------------------------------------------------------------------------

def test_a_windbot_deck_keeps_its_extra_deck():
    from game.card.ydke import Deck

    deck = Deck.from_windbot_format("#main\n1\n2\n#extra\n3\n!side\n4\n")

    assert deck.cards == [1, 2, 3]
    assert deck.side == [4]


def test_the_packet_listener_waits_instead_of_spinning(mocker):
    """No socket yet means wait, not burn a core."""
    import game.client as client_module

    sleeps = []
    mocker.patch("game.client.time.sleep", side_effect=lambda seconds: sleeps.append(seconds))

    class _Listener:
        expected_packet_id = None
        response_packet = None
        packet_event = MagicMock()

        def __init__(self):
            self.calls = 0

        @property
        def game_socket(self):
            self.calls += 1
            if self.calls == 1:
                return None
            socket = MagicMock()
            socket.recv.return_value = (None, None, None)
            return socket

        def _handle_disconnect(self):
            pass

    mocker.patch("game.client.wx.CallAfter", side_effect=lambda fn, *args: fn(*args))
    client_module.ORIGINAL_PACKET_LISTENER(_Listener())

    assert sleeps == [client_module.IDLE_POLL_SECONDS]


@pytest.mark.parametrize("key", [wx.WXK_SPACE])
def test_card_list_space_still_reads_the_current_card(mocker, key):
    card_list = _card_list(mocker)
    card_list.current_col = 1

    card_list.on_key_down(SimpleNamespace(GetKeyCode=lambda: key))

    from ui import card_list_ui

    assert "Details for B" in card_list_ui.utils.output.call_args.args[0]
