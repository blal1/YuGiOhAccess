"""Tests for interactive duel message handlers that create menus or require player response."""
import io
import struct
from unittest.mock import MagicMock, patch, PropertyMock


def _make_client(mocker, player_id=0):
    """Create a mock client with real binary read methods."""
    client = MagicMock()
    client.what_player_am_i = player_id
    client.read_u8 = lambda buf: struct.unpack('B', buf.read(1))[0]
    client.read_u16 = lambda buf: struct.unpack('<H', buf.read(2))[0]
    client.read_u32 = lambda buf: struct.unpack('<I', buf.read(4))[0]
    client.read_u64 = lambda buf: struct.unpack('<Q', buf.read(8))[0]

    def read_location(buf):
        controller = struct.unpack('B', buf.read(1))[0]
        location = struct.unpack('B', buf.read(1))[0]
        sequence = struct.unpack('<I', buf.read(4))[0]
        position = struct.unpack('<I', buf.read(4))[0]
        return controller, location, sequence, position
    client.read_location = read_location
    return client


# ============================================================
# select_chain (id 16)
# ============================================================

class TestSelectChain:
    def test_empty_chain_sends_minus_one(self, mocker):
        """Empty chain (size=0, spe_count=0) auto-responds -1."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_chain.Card")
        mocker.patch("ui.duel_messages.select_chain.LocationConversion")

        from ui.duel_messages.select_chain import select_chain
        from game.edo import structs
        client = MagicMock()
        client.what_player_am_i = 0
        select_chain(client, 0, 0, 0, 0, [])
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('i', -1))

    def test_opponent_chain_outputs_message(self, mocker):
        """When opponent selects chain, output message only."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_chain.Card")
        mocker.patch("ui.duel_messages.select_chain.LocationConversion")

        from ui.duel_messages.select_chain import select_chain
        client = MagicMock()
        client.what_player_am_i = 0
        # player=1, not our player
        mock_card = MagicMock()
        mock_card.get_effect_description.return_value = ""
        chains = [(0, mock_card, 0)]
        select_chain(client, 1, 1, 0, 0, chains)
        from core import utils
        utils.output.assert_called()
        client.send.assert_not_called()

    def test_forced_chain_no_cancel_message(self, mocker):
        """Forced chain does not announce 'press escape to cancel'."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mock_loc = mocker.patch("ui.duel_messages.select_chain.LocationConversion")
        mock_loc.from_card_location.return_value = MagicMock(to_zone_key=lambda: "zone1")

        from ui.duel_messages.select_chain import select_chain
        client = MagicMock()
        client.what_player_am_i = 0
        mock_card = MagicMock()
        mock_card.get_effect_description.return_value = ""
        chains = [(0, mock_card, 0)]
        select_chain(client, 0, 1, 0, 1, chains)  # forced=1
        from core import utils
        # Should output "Chaining" not "Chaining, Press escape..."
        calls = [str(c) for c in utils.output.call_args_list]
        assert not any("escape" in c.lower() for c in calls)

    def test_msg_select_chain_parses_data(self, mocker):
        """msg_select_chain correctly parses binary packet."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mock_card_cls = mocker.patch("ui.duel_messages.select_chain.Card")
        mock_card = MagicMock()
        mock_card.get_effect_description.return_value = ""
        mock_card_cls.return_value = mock_card
        mock_loc = mocker.patch("ui.duel_messages.select_chain.LocationConversion")
        mock_loc.from_card_location.return_value = MagicMock(to_zone_key=lambda: "zone1")

        client = _make_client(mocker, player_id=0)

        # Build packet: id(1) + player(1) + spe_count(1) + forced(1) + hint_timing(4) + other_timing(4) + size(4) + [code(4)+loc(10)+desc(8)+et(1)] per card
        data = b'\x10'  # msg id 16
        data += struct.pack('B', 0)  # player
        data += struct.pack('B', 0)  # spe_count
        data += struct.pack('B', 0)  # forced
        data += struct.pack('<I', 0)  # hint_timing
        data += struct.pack('<I', 0)  # other_timing
        data += struct.pack('<I', 0)  # size=0 (empty chain)

        from ui.duel_messages.select_chain import msg_select_chain
        msg_select_chain(client, data, len(data))
        # Empty chain → sends -1
        client.send.assert_called()


# ============================================================
# select_effect_yes_or_no (id 12)
# ============================================================

class TestSelectEffectYesNo:
    def test_yes_sends_one(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_effect_yes_or_no import yes
        from game.edo import structs
        client = MagicMock()
        yes(client)
        mock_ui_stack.pop_ui.assert_called_once()
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 1))

    def test_no_sends_zero(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_effect_yes_or_no import no
        from game.edo import structs
        client = MagicMock()
        no(client)
        mock_ui_stack.pop_ui.assert_called_once()
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 0))

    def test_select_effectyn_creates_menu(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_effect_yes_or_no.VerticalMenu")

        from ui.duel_messages.select_effect_yes_or_no import select_effectyn
        client = MagicMock()
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Dark Magician"
        mock_card.get_effect_description.return_value = ""
        select_effectyn(client, 0, mock_card, 0)
        mock_ui_stack.push_ui.assert_called_once()

    def test_msg_select_effectyn_parses(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_effect_yes_or_no.VerticalMenu")
        mock_card_cls = mocker.patch("ui.duel_messages.select_effect_yes_or_no.Card")
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Test"
        mock_card.get_effect_description.return_value = ""
        mock_card_cls.return_value = mock_card

        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + code(4) + location(10) + desc(8)
        data = b'\x0c'
        data += struct.pack('B', 0)  # player
        data += struct.pack('<I', 12345)  # card code
        data += struct.pack('B', 0) + struct.pack('B', 2) + struct.pack('<I', 0) + struct.pack('<I', 0)  # location
        data += struct.pack('<Q', 0)  # desc

        from ui.duel_messages.select_effect_yes_or_no import msg_select_effectyn
        msg_select_effectyn(client, data, len(data))
        mock_ui_stack.push_ui.assert_called_once()


# ============================================================
# select_yes_no (id 13)
# ============================================================

class TestSelectYesNo:
    def test_yes_sends_one(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_yes_no import yes
        from game.edo import structs
        client = MagicMock()
        yes(client)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 1))

    def test_no_sends_zero(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_yes_no import no
        from game.edo import structs
        client = MagicMock()
        no(client)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 0))

    def test_select_yes_no_with_code(self, mocker):
        """When desc has a card code, creates menu with card name."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_yes_no.VerticalMenu")
        mock_card_cls = mocker.patch("ui.duel_messages.select_yes_no.Card")
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Blue-Eyes"
        mock_card.get_effect_description.return_value = "Destroy one card."
        mock_card_cls.return_value = mock_card
        mock_lang = MagicMock()
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_yes_no.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.select_yes_no import select_yes_no
        client = MagicMock()
        # desc with code=100, stringid=0 → code=100<<20 | 0
        desc = (100 << 20) | 0
        select_yes_no(client, 0, desc)
        from ui.duel_messages import select_yes_no as select_yes_no_module
        first_label = select_yes_no_module.VerticalMenu.return_value.append_item.call_args_list[0].args[0]
        assert "Blue-Eyes" in first_label
        assert "Destroy one card." in first_label
        mock_ui_stack.push_ui.assert_called_once()

    def test_select_yes_no_system_string(self, mocker):
        """When desc has code=0, uses system strings."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_yes_no.VerticalMenu")
        mock_lang = MagicMock()
        mock_lang.strings = {'system': {1: "Do you want to proceed?"}}
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_yes_no.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.select_yes_no import select_yes_no
        client = MagicMock()
        desc = 1  # code=0, stringid=1
        select_yes_no(client, 0, desc)
        mock_ui_stack.push_ui.assert_called_once()

    def test_msg_select_yesno_parses(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_yes_no.VerticalMenu")
        mock_lang = MagicMock()
        mock_lang.strings = {'system': {5: "Continue?"}}
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_yes_no.variables.LANGUAGE_HANDLER", mock_lang)

        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + desc(8)
        data = b'\x0d'
        data += struct.pack('B', 0)
        data += struct.pack('<Q', 5)  # code=0, stringid=5

        from ui.duel_messages.select_yes_no import msg_select_yesno
        msg_select_yesno(client, data, len(data))
        mock_ui_stack.push_ui.assert_called_once()


# ============================================================
# select_option (id 14)
# ============================================================

class TestSelectOption:
    def test_select_function_sends_index(self, mocker):
        """select() sends the chosen index."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mock_lang = MagicMock()
        mock_lang.strings = {'system': {1: "Option A"}}
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_option.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.select_option import select
        from game.edo import structs
        client = MagicMock()
        options = [1, 2]  # code=0, stringid=1,2
        select(client, options, 0)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 0))

    def test_select_option_with_card_code(self, mocker):
        """select() with card code reads card strings."""
        mocker.patch("core.utils.output")
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mock_card_cls = mocker.patch("ui.duel_messages.select_option.Card")
        mock_card = MagicMock()
        mock_card.strings = {0: "Destroy monster"}
        mock_card_cls.return_value = mock_card

        from ui.duel_messages.select_option import select
        from game.edo import structs
        client = MagicMock()
        options = [(100 << 20) | 0]  # code=100, stringid=0
        select(client, options, 0)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 0))

    def test_select_option_creates_menu(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_option.VerticalMenu")
        mock_lang = MagicMock()
        mock_lang.strings = {'system': {1: "Opt A", 2: "Opt B"}}
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_option.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.select_option import select_option
        client = MagicMock()
        options = [1, 2]
        select_option(client, 0, options)
        mock_ui_stack.push_ui.assert_called_once()

    def test_msg_select_option_parses(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_option.VerticalMenu")
        mock_lang = MagicMock()
        mock_lang.strings = {'system': {1: "Opt"}}
        mock_lang._ = lambda s: s
        mocker.patch("ui.duel_messages.select_option.variables.LANGUAGE_HANDLER", mock_lang)

        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + size(1) + options(8 each)
        data = b'\x0e'
        data += struct.pack('B', 0)  # player
        data += struct.pack('B', 2)  # size=2
        data += struct.pack('<Q', 1)  # option 1
        data += struct.pack('<Q', 2)  # option 2

        from ui.duel_messages.select_option import msg_select_option
        msg_select_option(client, data, len(data))
        mock_ui_stack.push_ui.assert_called_once()


# ============================================================
# select_position (id 19)
# ============================================================

class TestSelectPosition:
    def test_set_position_sends_value(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_position import set_position
        from game.edo import structs
        client = MagicMock()
        set_position(client, 4)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 4))

    def test_select_position_creates_menu(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_position.VerticalMenu")
        from game.card import card_constants

        from ui.duel_messages.select_position import select_position
        client = MagicMock()
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Monster"
        # All positions available
        positions = card_constants.POSITION(0x0F)
        select_position(client, 0, mock_card, positions)
        mock_ui_stack.push_ui.assert_called_once()

    def test_msg_select_position_parses(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_position.VerticalMenu")
        mock_card_cls = mocker.patch("ui.duel_messages.select_position.Card")
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Test"
        mock_card_cls.return_value = mock_card

        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + code(4) + positions(1)
        data = b'\x13'
        data += struct.pack('B', 0)
        data += struct.pack('<I', 12345)
        data += struct.pack('B', 5)  # face-up attack + face-up defense

        from ui.duel_messages.select_position import msg_select_position
        msg_select_position(client, data, len(data))
        mock_ui_stack.push_ui.assert_called_once()


# ============================================================
# select_place (id 18, 24)
# ============================================================

class TestSelectPlace:
    def test_select_place_single_zone(self, mocker):
        """Select 1 zone outputs message."""
        mocker.patch("core.utils.output")
        mock_loc = mocker.patch("ui.duel_messages.select_place.LocationConversion")
        mock_loc_inst = MagicMock()
        mock_loc_inst.to_human_readable.return_value = "Monster Zone 1"
        mock_loc.from_zone_key.return_value = mock_loc_inst
        from ui.duel_messages.select_place import select_place
        client = MagicMock()
        client.flag_to_usable_cardspecs.return_value = ["spec1"]
        select_place(client, 0, 1, 0)
        from core import utils
        utils.output.assert_called()

    def test_select_place_multi_zone(self, mocker):
        """Select multiple zones outputs count message."""
        mocker.patch("core.utils.output")
        mock_loc = mocker.patch("ui.duel_messages.select_place.LocationConversion")
        mock_loc_inst = MagicMock()
        mock_loc_inst.to_human_readable.return_value = "Zone"
        mock_loc.from_zone_key.return_value = mock_loc_inst
        from ui.duel_messages.select_place import select_place
        client = MagicMock()
        client.flag_to_usable_cardspecs.return_value = ["spec1", "spec2"]
        select_place(client, 0, 2, 0)
        from core import utils
        utils.output.assert_called()

    def test_resolve_select_place_sends_response(self, mocker):
        from ui.duel_messages.select_place import resolve_select_place
        from game.edo import structs
        client = MagicMock()
        client.useful_spec_to_location.return_value = (4, 0, False)  # location=4, seq=0, not opponent

        mock_zone = MagicMock()
        mock_zone.label = "p_mz_0"
        resolve_select_place(client, 0, [mock_zone], lambda: None)
        client.send.assert_called()

    def test_resolve_select_place_sends_multiple_zones_once(self, mocker):
        from ui.duel_messages.select_place import resolve_select_place
        from game.edo import structs

        client = MagicMock()
        client.useful_spec_to_location.side_effect = [
            (4, 0, False),
            (8, 1, True),
        ]
        zones = [MagicMock(label="pm0"), MagicMock(label="os1")]
        old_handler = lambda: None

        resolve_select_place(client, 0, zones, old_handler)

        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, bytes([0, 4, 0, 1, 8, 1]))
        client.get_duel_field.return_value.handle_enter = old_handler

    def test_process_selected_zone_invalid(self, mocker):
        """Invalid zone selection outputs error."""
        mocker.patch("core.utils.output")
        mocker.patch("ui.duel_messages.select_place.LocationConversion")

        from ui.duel_messages.select_place import process_selected_zone
        client = MagicMock()
        client.get_duel_field.return_value.get_zone_from_current_position.return_value = None
        process_selected_zone(client, 0, 1, [], lambda: None)
        from core import utils
        assert any("Invalid" in str(c) for c in utils.output.call_args_list)

    def test_msg_select_place_parses(self, mocker):
        """msg_select_place parses count and flag."""
        mocker.patch("core.utils.output")
        mock_loc = mocker.patch("ui.duel_messages.select_place.LocationConversion")
        mock_loc_inst = MagicMock()
        mock_loc_inst.to_human_readable.return_value = "Zone"
        mock_loc.from_zone_key.return_value = mock_loc_inst
        client = _make_client(mocker, player_id=0)
        client.flag_to_usable_cardspecs = MagicMock(return_value=["spec1"])
        client.get_duel_field = MagicMock()

        # The msg_select_place reads from data WITHOUT slicing [1:]
        # id(1) + player(1) + count(1) + flag(4)
        data = b'\x12'
        data += struct.pack('B', 0)  # player
        data += struct.pack('B', 1)  # count
        data += struct.pack('<I', 0xFF)  # flag

        from ui.duel_messages.select_place import msg_select_place
        msg_select_place(client, data, len(data))
        client.flag_to_usable_cardspecs.assert_called()


# ============================================================
# select_battlecmd (id 10)
# ============================================================

class TestSelectBattlecmd:
    def test_display_battle_menu_empty(self, mocker):
        """Empty card lists clears tab order."""
        from ui.duel_messages.select_battlecmd import display_battle_menu
        client = MagicMock()
        client.player.activatable = []
        client.player.attackable = []
        display_battle_menu(client)
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with([])

    def test_display_battle_menu_with_cards(self, mocker):
        """Cards in lists update tab order."""
        from ui.duel_messages.select_battlecmd import display_battle_menu

        TestCard = type("TestCard", (), {})
        mocker.patch("ui.duel_messages.select_battlecmd.Card", TestCard)
        mock_card = TestCard()
        client = MagicMock()
        client.player.activatable = [mock_card]
        client.player.attackable = []

        mock_zone = MagicMock()
        mock_zone.card = mock_card
        client.get_duel_field.return_value.zones = {"zone1": mock_zone}
        display_battle_menu(client)
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with(["zone1"])

        client.get_duel_field.return_value.zones = {"bad": MagicMock(card=object())}
        display_battle_menu(client)
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with([])

    def test_display_battle_menu_matches_duel_location_not_just_code(self, mocker):
        """Only the currently actionable zone is included in tab order."""
        from ui.duel_messages.select_battlecmd import display_battle_menu

        class TestCard:
            def __init__(self, sequence):
                self.code = 1
                self.controller = 0
                self.location = 4
                self.sequence = sequence

        mocker.patch("ui.duel_messages.select_battlecmd.Card", TestCard)
        client = MagicMock()
        client.player.activatable = [TestCard(1)]
        client.player.attackable = []
        client.get_duel_field.return_value.zones = {
            "ph0": MagicMock(card=TestCard(0)),
            "ph1": MagicMock(card=TestCard(1)),
        }

        display_battle_menu(client)

        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with(["ph1"])

    def test_msg_select_battlecmd_parses(self, mocker):
        """msg_select_battlecmd parses and sets player state."""
        mocker.patch("ui.duel_messages.select_battlecmd.Card")
        client = _make_client(mocker, player_id=0)
        client.player = MagicMock()
        activatable = [MagicMock()]
        attackable = [MagicMock()]
        client.read_cardlist = MagicMock(side_effect=[activatable, attackable])
        client.get_duel_field = MagicMock()

        from ui.duel_messages.select_battlecmd import msg_select_battlecmd
        data = b'\x0a' + struct.pack('BBB', 0, 1, 0)
        msg_select_battlecmd(client, data, len(data))
        client.player.clear_all.assert_called_once()
        assert client.player.activatable == activatable
        assert client.player.attackable == attackable
        assert client.player.can_go_to_main_phase2 == 1
        assert client.player.can_go_to_end_phase == 0
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called()


# ============================================================
# select_unselect_card (id 26)
# ============================================================

class TestSelectUnselectCard:
    def test_select_specific_card_sends_index(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_unselect_card import select_unselect_specific_card
        from game.edo import structs
        client = MagicMock()
        select_unselect_specific_card(client, 3)
        expected = struct.pack('I', 1) + struct.pack('I', 3)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, expected)

    def test_select_specific_card_cancel(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.select_unselect_card import select_unselect_specific_card
        from game.edo import structs
        client = MagicMock()
        select_unselect_specific_card(client, -1)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('i', -1))

    def test_select_unselect_card_creates_menu(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.select_unselect_card.VerticalMenu")
        mock_loc = mocker.patch("ui.duel_messages.select_unselect_card.LocationConversion")
        mock_loc.from_card_location.return_value = MagicMock(to_human_readable=lambda: "Hand")

        from ui.duel_messages.select_unselect_card import select_unselect_card
        client = MagicMock()
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Monster"
        select_unselect_card(client, 0, 0, 1, 1, 3, [mock_card], [])
        mock_ui_stack.push_ui.assert_called_once()

    def test_select_unselect_with_finish(self, mocker):
        """Finishable adds a Finish button."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mock_menu = MagicMock()
        mocker.patch("ui.duel_messages.select_unselect_card.VerticalMenu", return_value=mock_menu)
        mock_loc = mocker.patch("ui.duel_messages.select_unselect_card.LocationConversion")
        mock_loc.from_card_location.return_value = MagicMock(to_human_readable=lambda: "Hand")

        from ui.duel_messages.select_unselect_card import select_unselect_card
        client = MagicMock()
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Card"
        select_unselect_card(client, 0, 1, 0, 1, 3, [mock_card], [])  # finishable=1, cancelable=0
        # Should have "Finish" item
        append_calls = mock_menu.append_item.call_args_list
        assert any("Finish" in str(c) for c in append_calls)


# ============================================================
# announce_card (id 142)
# ============================================================

class TestAnnounceCard:
    def test_send_response_pops_and_sends(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.announce_card import _send_response
        from game.edo import structs
        client = MagicMock()
        _send_response(client, 12345, True)
        mock_ui_stack.pop_ui.assert_called_once()
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 12345))

    def test_send_response_no_pop(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.announce_card import _send_response
        client = MagicMock()
        _send_response(client, 67890, False)
        mock_ui_stack.pop_ui.assert_not_called()
        client.send.assert_called_once()

    def test_announce_card_single_match(self, mocker):
        """Single card match sends directly."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")
        mocker.patch("ui.duel_messages.announce_card.InputUI").return_value.show.return_value = "Blue"
        mock_lang = MagicMock()
        mock_lang.get_cards_by_partial_name.return_value = {"Blue-Eyes": 89631139}
        mocker.patch("ui.duel_messages.announce_card.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.announce_card import announce_card
        from game.edo import structs
        client = MagicMock()
        announce_card(client, 0, [])
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('I', 89631139))

    def test_announce_card_multiple_matches(self, mocker):
        """Multiple matches creates selection menu."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")
        mocker.patch("ui.duel_messages.announce_card.InputUI").return_value.show.return_value = "Blue"
        mocker.patch("ui.duel_messages.announce_card.VerticalMenu")
        mock_lang = MagicMock()
        mock_lang.get_cards_by_partial_name.return_value = {"Blue-Eyes": 89631139, "Blue Dragon": 11111}
        mocker.patch("ui.duel_messages.announce_card.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.announce_card import announce_card
        announce_card(MagicMock(), 0, [])
        mock_ui_stack.push_ui.assert_called()

    def test_announce_card_no_match(self, mocker):
        """No match outputs error and recurses (mocked to prevent infinite)."""
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("core.utils.output")
        # First call returns nothing, second returns a match to break recursion
        input_mock = mocker.patch("ui.duel_messages.announce_card.InputUI")
        input_mock.return_value.show.side_effect = ["nope", "Blue"]
        mock_lang = MagicMock()
        mock_lang.get_cards_by_partial_name.side_effect = [{}, {"Blue-Eyes": 89631139}]
        mocker.patch("ui.duel_messages.announce_card.variables.LANGUAGE_HANDLER", mock_lang)

        from ui.duel_messages.announce_card import announce_card
        client = MagicMock()
        announce_card(client, 0, [])
        from core import utils
        assert any("No cards found" in str(c) for c in utils.output.call_args_list)


# ============================================================
# announce_number (id 143)
# ============================================================

class TestAnnounceNumber:
    def test_send_response(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)

        from ui.duel_messages.announce_number import _send_response
        from game.edo import structs
        client = MagicMock()
        options = [1, 2, 3]
        _send_response(client, options, 1)
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('i', 1))
        mock_ui_stack.pop_ui.assert_called_once()

    def test_announce_number_creates_menu(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.announce_number.VerticalMenu")

        from ui.duel_messages.announce_number import announce_number
        client = MagicMock()
        announce_number(client, 0, [1, 2, 5])
        mock_ui_stack.push_ui.assert_called_once()

    def test_msg_announce_number_parses(self, mocker):
        mock_ui_stack = MagicMock()
        mocker.patch("core.utils.get_ui_stack", return_value=mock_ui_stack)
        mocker.patch("ui.duel_messages.announce_number.VerticalMenu")

        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + size(1) + options(8 each)
        data = b'\x8f'  # 143
        data += struct.pack('B', 0)
        data += struct.pack('B', 3)
        data += struct.pack('<Q', 1)
        data += struct.pack('<Q', 2)
        data += struct.pack('<Q', 3)

        from ui.duel_messages.announce_number import msg_announce_number
        msg_announce_number(client, data, len(data))
        assert mock_ui_stack.push_ui.called


# ============================================================
# sort_chain (id 21)
# ============================================================

class TestSortChain:
    def test_sort_chain_sends_minus_one(self, mocker):
        """sort_chain always auto-responds -1 (no player input needed)."""
        from ui.duel_messages.sort_chain import sort_chain
        from game.edo import structs
        client = MagicMock()
        sort_chain(client, 0, [])
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('i', -1))

    def test_msg_sort_chain_parses(self, mocker):
        mocker.patch("ui.duel_messages.sort_chain.Card")
        client = _make_client(mocker, player_id=0)

        # id(1) + player(1) + size(4) + [code(4) + controller(1) + location(4) + sequence(4)] per card
        data = b'\x15'  # 21
        data += struct.pack('B', 0)  # player
        data += struct.pack('<I', 1)  # size=1
        data += struct.pack('<I', 11111)  # code
        data += struct.pack('B', 0)  # controller
        data += struct.pack('<I', 2)  # location
        data += struct.pack('<I', 0)  # sequence

        from ui.duel_messages.sort_chain import msg_sort_chain
        from game.edo import structs
        msg_sort_chain(client, data, len(data))
        client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack('i', -1))


# ============================================================
# confirm_cards (id 31)
# ============================================================

class TestConfirmCards:
    def test_confirm_cards_player_shows(self, mocker):
        """When to_player != our player, 'You shows Your opponent'."""
        mocker.patch("core.utils.output")
        from ui.duel_messages.confirm_cards import confirm_cards
        client = MagicMock()
        client.what_player_am_i = 0
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Dark Magician"
        confirm_cards(client, 1, 1, [mock_card])  # to_player=1, we are 0
        from core import utils
        assert utils.output.call_count >= 2  # header + card name

    def test_confirm_cards_opponent_shows(self, mocker):
        """When to_player == our player, 'Your opponent shows You'."""
        mocker.patch("core.utils.output")
        from ui.duel_messages.confirm_cards import confirm_cards
        client = MagicMock()
        client.what_player_am_i = 0
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Blue-Eyes"
        confirm_cards(client, 0, 1, [mock_card])  # to_player=0 == us
        from core import utils
        assert utils.output.call_count >= 2

    def test_msg_confirm_cards_parses(self, mocker):
        mocker.patch("core.utils.output")
        mock_card_cls = mocker.patch("ui.duel_messages.confirm_cards.Card")
        mock_card = MagicMock()
        mock_card.get_name.return_value = "Test"
        mock_card_cls.return_value = mock_card
        client = _make_client(mocker, player_id=0)
        # id(1) + player(1) + size(4) + [code(4) + controller(1) + location(1) + sequence(4)] per card
        data = b'\x1f'  # 31
        data += struct.pack('B', 1)  # player=1 (not us)
        data += struct.pack('<I', 1)  # size=1
        data += struct.pack('<I', 55555)  # code
        data += struct.pack('B', 0)  # controller
        data += struct.pack('B', 2)  # location
        data += struct.pack('<I', 0)  # sequence

        from ui.duel_messages.confirm_cards import msg_confirm_cards
        msg_confirm_cards(client, data, len(data))
        from core import utils
        assert utils.output.called


# ============================================================
# idle (id 11)
# ============================================================

class TestIdle:
    def test_idle_not_my_turn(self, mocker):
        """When player != what_player_am_i, returns early."""
        client = _make_client(mocker, player_id=0)
        client.read_cardlist = MagicMock(return_value=[])
        client.player = MagicMock()

        # Build minimal data
        data = b'\x0b'  # id 11
        data += struct.pack('B', 1)  # player=1 (not us=0)
        # read_cardlist is mocked so won't read more

        from ui.duel_messages.idle import msg_idlecmd
        result = msg_idlecmd(client, data, len(data))
        # Should return early without setting player state
        client.player.clear_all.assert_not_called()

    def test_idle_sets_player_state(self, mocker):
        """When it's our turn, sets player card lists and tab order."""
        mocker.patch("ui.duel_messages.idle.Card")
        client = _make_client(mocker, player_id=0)
        client.read_cardlist = MagicMock(return_value=[])
        client.player = MagicMock()
        client.get_duel_field = MagicMock()

        data = b'\x0b'
        data += struct.pack('B', 0)  # player=0 (us)
        data += struct.pack('BBB', 1, 1, 0)  # to_bp, to_ep, can_shuffle

        from ui.duel_messages.idle import msg_idlecmd
        msg_idlecmd(client, data, len(data))
        client.player.clear_all.assert_called_once()
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called()

    def test_idle_with_cards_updates_tab(self, mocker):
        """Cards in lists appear in tab order."""
        TestCard = type("TestCard", (), {})
        mock_card = TestCard()
        mocker.patch("ui.duel_messages.idle.Card", TestCard)

        client = _make_client(mocker, player_id=0)
        client.read_cardlist = MagicMock(return_value=[mock_card])
        client.player = MagicMock()
        mock_zone = MagicMock()
        mock_zone.card = mock_card
        client.get_duel_field = MagicMock()
        client.get_duel_field.return_value.zones = {"zone1": mock_zone}

        data = b'\x0b' + struct.pack('B', 0) + struct.pack('BBB', 1, 1, 0)

        from ui.duel_messages.idle import msg_idlecmd
        msg_idlecmd(client, data, len(data))
        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with(["zone1"])

    def test_idle_tab_order_uses_exact_duel_location(self, mocker):
        """Duplicate cards in other zones are not tabbable."""
        from ui.duel_messages.idle import idle

        class TestCard:
            def __init__(self, sequence):
                self.code = 10
                self.controller = 0
                self.location = 2
                self.sequence = sequence

        mocker.patch("ui.duel_messages.idle.Card", TestCard)
        client = MagicMock()
        client.player.summonable = [TestCard(2)]
        client.player.special_summonable = []
        client.player.repositionable = []
        client.player.monster_settable = []
        client.player.spell_settable = []
        client.player.activatable = []
        client.get_duel_field.return_value.zones = {
            "ph0": MagicMock(card=TestCard(0)),
            "ph2": MagicMock(card=TestCard(2)),
        }

        idle(client, 0)

        client.get_duel_field.return_value.tab_order.set_tabable_items.assert_called_with(["ph2"])


def test_chain_end_clears_the_chain():
    """MSG_CHAIN_END, not MSG_CHAIN_SOLVED, is what ends the chain."""
    from ui.duel_messages.chained import msg_chain_end

    client = _make_client(None, player_id=0)
    client.player = MagicMock()
    client.player.chaining_cards = [MagicMock()]
    client.player.chain_stack = [MagicMock()]

    msg_chain_end(client, b"\x4a", 1)

    assert client.player.chaining_cards == []
    assert client.player.chain_stack == []
