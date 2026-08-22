import struct
from unittest.mock import MagicMock


def _make_field(mocker):
    from ui.duel_field import DuelField

    field = DuelField.__new__(DuelField)
    field.rows = 8
    field.cols = 60
    field.center_x = 29.5
    field.center_y = 3.5
    field.current_row = 0
    field.current_col = 0
    field.opponent_hand_row = 0
    field.opponent_spell_and_trap_row = 1
    field.opponent_monster_row = 2
    field.extra_monster_row = 3
    field.player_monster_row = 4
    field.player_spell_and_trap_row = 5
    field.player_hand_row = 6
    field.extra_information_row = 7
    field.amount_of_zones = 4
    field.cells = [[None for _ in range(field.cols)] for _ in range(field.rows)]
    field.cell_functions = [[None for _ in range(field.cols)] for _ in range(field.rows)]
    field.zones = {}
    field.tab_order = MagicMock()
    field.sound_positions = {(row, col): {"x": col, "y": row} for row in range(field.rows) for col in range(field.cols)}
    field._preemtive_key_handler = None
    field.client = MagicMock()
    field.client.what_player_am_i = 0
    field.client.is_it_my_turn = True
    field.client.player.activatable = []
    field.client.player.chaining_cards = []
    field.client.player.attackable = []
    field.client.player.summonable = []
    field.client.player.special_summonable = []
    field.client.player.repositionable = []
    field.client.player.monster_settable = []
    field.client.player.spell_settable = []
    mocker.patch("ui.duel_field.utils.output")
    mocker.patch("ui.duel_field.variables.config", {"helper_zones": True})
    return field


class FakeCard:
    def __init__(self, code=1):
        from game.card import card_constants

        self.code = code
        self.name = f"Card {code}"
        self.type = card_constants.TYPE.MONSTER
        self.attack = 1000
        self.defense = 1000
        self.controller = 0
        self.location = card_constants.LOCATION.MONSTER_ZONE
        self.sequence = 0
        self.position = card_constants.POSITION.FACE_UP_ATTACK
        self.chain_index = 7
        self.lscale = 1
        self.rscale = 8
        self.effect_description = ""

    def set_location_and_position_info(self, controller, location, sequence, position):
        self.controller = controller
        self.location = location
        self.sequence = sequence
        self.position = position

    def get_name(self):
        return self.name

    def get_link_markers(self):
        return "bottom, top"

    def __str__(self):
        return self.name

    def __eq__(self, other):
        return getattr(other, "code", None) == self.code and getattr(other, "sequence", None) == self.sequence


def _query(**kwargs):
    q = MagicMock()
    q.onfield_skipped = kwargs.pop("onfield_skipped", False)
    for key, value in kwargs.items():
        setattr(q, key, value)
    return q


def test_zone_properties_follow_card(mocker):
    from game.card import card_constants
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    card = FakeCard(10)
    zone = Zone("z", card)
    assert zone.controller == 0
    assert zone.location == card_constants.LOCATION.MONSTER_ZONE
    assert zone.sequence == 0
    assert zone.position == card_constants.POSITION.FACE_UP_ATTACK
    assert str(zone) == "z"
    assert zone == Zone("z", "empty")

    text_zone = Zone("t", "empty")
    text_zone.controller = 1
    text_zone.location = 2
    text_zone.sequence = 3
    text_zone.position = 4
    assert (text_zone.controller, text_zone.location, text_zone.sequence, text_zone.position) == (1, 2, 3, 4)


def test_duel_field_real_initializer_with_wx_patched(mocker):
    from ui.base_ui import BaseUI
    from ui.duel_field import DuelField

    frame = MagicMock()
    mocker.patch("ui.base_ui.wx.GetTopLevelWindows", return_value=[frame])
    mocker.patch("ui.base_ui.wx.Panel.__init__", return_value=None)
    mocker.patch("ui.base_ui.wx.GridSizer", return_value=MagicMock())
    mocker.patch.object(BaseUI, "SetSizer", MagicMock())
    mocker.patch.object(BaseUI, "Fit", MagicMock())
    mocker.patch.object(BaseUI, "Bind", MagicMock())
    mocker.patch.object(BaseUI, "SetFocus", MagicMock())
    mocker.patch.object(BaseUI, "Layout", MagicMock())
    mocker.patch("ui.duel_field.variables.config", {"helper_zones": True})

    client = MagicMock()
    field = DuelField(client)

    assert field.client is client
    assert field.rows == 8
    assert field.cols == 60
    assert "pm0" in field.zones
    assert field.preemtive_key_handler is None


def test_setup_field_and_zone_setters(mocker):
    field = _make_field(mocker)
    field.setup_field()

    assert "pm0" in field.zones
    assert "om4" in field.zones
    assert "og0" in field.zones
    assert "pg0" in field.zones
    assert "or0" in field.zones
    assert "pr0" in field.zones
    assert "q0" in field.zones
    assert "pd" in field.zones
    assert field.cells[int(field.center_y)][int(field.center_x)] == "BLANK"
    assert "DuelField" in str(field)

    field.set_extra_monster_zone(99, "bad")
    assert "q99" in field.zones


def test_all_field_zones_have_spatial_audio_positions(mocker):
    field = _make_field(mocker)
    field.setup_field()

    query = _query(controller=1, location=0, sequence=0, position=0)
    field.append_card_to_player_hand(FakeCard(101))
    field.append_card_to_opponent_hand(FakeCard(102), query)
    field.append_card_to_player_extra_deck(FakeCard(103))
    field.append_card_to_opponent_extra_deck(FakeCard(104), query)
    field.append_card_to_player_graveyard(FakeCard(105))
    field.append_card_to_opponent_graveyard(FakeCard(106), query)
    field.append_card_to_player_banished(FakeCard(107))
    field.append_card_to_opponent_banished(FakeCard(108), query)

    expected_zone_keys = [
        "oh0", "os0", "om0", "q0", "q1", "pm0", "ps0", "ph0",
        "ox0", "ox1", "px0", "px1", "opf", "pf", "og0", "og1",
        "pg0", "pg1", "or0", "or1", "pr0", "pr1", "od", "pd",
    ]
    for zone_key in expected_zone_keys:
        assert field.get_sound_position_for_zone(zone_key) is not None, zone_key

    assert field.get_sound_position_for_zone("px1") == field.sound_positions[(field.player_spell_and_trap_row, int(field.center_x - 3))]
    assert field.get_sound_position_for_zone("og1") == field.sound_positions[(field.opponent_monster_row, int(field.center_x - 3))]


def test_card_information_labels_chain_and_cell_change(mocker):
    from game.card import card_constants
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    card = FakeCard(1)
    field.client.player.activatable = [card]
    field.client.player.chaining_cards = [card]
    field.client.player.attackable = [card]
    field.client.player.summonable = [card]
    field.client.player.special_summonable = [card]
    field.client.player.repositionable = [card]
    field.client.player.monster_settable = [card]
    zone = Zone("pm0", card)
    field.zones = {"pm0": zone}
    field.cells[0][0] = "pm0"

    info = field.get_card_information_to_show_when_card_is_selected(zone)
    assert "Has activatable effects" in info
    assert "Card 1" in info
    assert card_constants.POSITION.FACE_UP_ATTACK.name in info

    field.on_cell_change(0, 0, 0, 0, "pm0")
    from ui.duel_field import utils
    utils.output.assert_called()

    facedown = FakeCard(0)
    assert field.get_card_information_to_show_when_card_is_selected(Zone("x", facedown)) == "Face down card"
    assert field.get_card_information_to_show_when_card_is_selected(Zone("x", "Empty")) == "Empty"


def test_card_information_labels_use_duel_identity(mocker):
    from game.card import card_constants
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    zone_card = FakeCard(42)
    zone_card.set_location_and_position_info(0, card_constants.LOCATION.HAND, 2, card_constants.POSITION.FACE_UP)
    playable = FakeCard(42)
    playable.set_location_and_position_info(0, card_constants.LOCATION.HAND, 2, card_constants.POSITION.FACE_DOWN)
    field.client.player.summonable = [playable]
    field.client.player.spell_settable = [playable]

    info = field.get_card_information_to_show_when_card_is_selected(Zone("ph2", zone_card))

    assert "Summonable" in info
    assert "Settable" in info


def test_card_accessibility_details_and_chain_stack(mocker):
    from game.card import card_constants
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    card = FakeCard(1)
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.XYZ | card_constants.TYPE.PENDULUM | card_constants.TYPE.LINK
    card.xyz_materials = [FakeCard(2), FakeCard(3)]
    card.effect_description = "Destroy one card."
    zone = Zone("pm0", card)
    field.zones = {"pm0": zone}
    field.cells[0][0] = "pm0"

    info = field.get_card_information_to_show_when_card_is_selected(zone)
    assert "XYZ materials (2)" in info
    assert "Pendulum scale" in info
    assert "Link Markers" in info
    assert "bottom" in info
    assert "top" in info
    assert "Destroy one card." in info
    assert field.get_sound_position_for_zone("pm0") == field.sound_positions[(0, 0)]

    field.client.player.chaining_cards = [card]
    assert "Current chain" in field.get_chain_stack_text()
    assert "Destroy one card." in field.get_chain_stack_text()

    no_material = FakeCard(4)
    no_material.type = card_constants.TYPE.MONSTER | card_constants.TYPE.XYZ
    no_material.xyz_materials = []
    no_material.location = card_constants.LOCATION.MONSTER_ZONE
    assert "No XYZ materials attached" in ", ".join(field.get_card_accessibility_details(no_material))

    no_description = FakeCard(5)
    field.client.player.chaining_cards = [no_description]
    assert "1: Card 5" in field.get_chain_stack_text()
    field.client.player.chaining_cards = []
    assert "No chain" in field.get_chain_stack_text()

    partial_link = FakeCard(6)
    partial_link.type = card_constants.TYPE.MONSTER
    partial_link.link_marker = 1
    partial_link.defense = 1
    assert "Link Markers" in field.get_card_accessibility_details(partial_link)[0]
    assert field.get_sound_position_for_zone("missing") is None
    assert field.get_sound_position_for_zone("pm0-missing") is None


def test_card_information_shortcuts(mocker):
    from game.card import card_constants
    from ui.duel_field import DuelField, Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    card = FakeCard(77)
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.PENDULUM | card_constants.TYPE.XYZ
    card.effect_description = "Quick effect text."
    card.xyz_materials = [FakeCard(1), FakeCard(2)]
    card.set_location_and_position_info(0, card_constants.LOCATION.MONSTER_ZONE, 1, card_constants.POSITION.FACE_UP_ATTACK)
    col = int(field.center_x - (field.amount_of_zones / 2)) + 1
    field.zones = {"pm1": Zone("pm1", card)}
    field.cells[field.player_monster_row][col] = "pm1"
    field.current_row = field.player_monster_row
    field.current_col = col
    field.client.player.activatable = [card]

    field.output_current_card_name()
    field.output_current_card_description()
    field.output_current_card_stats()
    field.output_current_card_location()
    field.output_current_card_actions()

    from ui.duel_field import utils
    output_text = "\n".join(str(call) for call in utils.output.call_args_list)
    assert "Card 77" in output_text
    assert "Quick effect text." in output_text
    assert "Attack:" in output_text
    assert "XYZ materials: 2" in output_text
    assert "FACE_UP_ATTACK" in output_text
    assert "Has activatable effects" in output_text

    event = MagicMock()
    event.ShiftDown.return_value = False
    for key in ("N", "D", "T", "L", "A"):
        event.GetKeyCode.return_value = ord(key)
        DuelField.on_key_down(field, event)


def test_resolve_chain_variants(mocker):
    from game.edo import structs
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    assert field.resolve_chain(None) is False
    assert field.resolve_chain("zone") is False
    assert field.resolve_chain(Zone("z", None)) is False
    assert field.resolve_chain(Zone("z", "not card")) is False

    card = FakeCard(1)
    field.client.player.chaining_cards = [card]
    assert field.resolve_chain(Zone("z", card)) is True
    field.client.send.assert_called_once_with(structs.ClientIdType.RESPONSE, struct.pack("I", 7))
    assert field.preemtive_key_handler is None


def test_handle_zone_updates_for_all_locations(mocker):
    from game.card import card_constants

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    field.setup_field()
    q = _query(code=10, controller=0, location=card_constants.LOCATION.HAND, sequence=0, position=1)
    field.update_field(field.client, 0, card_constants.LOCATION.HAND, [q])
    assert "ph0" in field.zones

    q.controller = 1
    field.update_field(field.client, 1, card_constants.LOCATION.HAND, [q])
    assert "oh0" in field.zones

    for location, keys in [
        (card_constants.LOCATION.EXTRA, ("px0", "ox0")),
        (card_constants.LOCATION.MONSTER_ZONE, ("pm0", "om0")),
        (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, ("ps0", "os0")),
    ]:
        q = _query(code=11, controller=0, location=location, sequence=0, position=1)
        field.update_field(field.client, 0, location, [q])
        assert keys[0] in field.zones
        q.controller = 1
        field.update_field(field.client, 1, location, [q])
        assert keys[1] in field.zones

    field.update_field(field.client, 0, card_constants.LOCATION.DECK, [])

    skipped = _query(code=99, controller=0, location=card_constants.LOCATION.HAND, sequence=9, position=1, onfield_skipped=True)
    field.handle_player_hand([skipped])
    assert "ph0" not in field.zones

    for handler, sequence, expected in [
        (field.handle_opponent_hand, 0, "oh0"),
        (field.handle_player_monster_zone, 5, "q0"),
        (field.handle_player_monster_zone, 6, "q1"),
        (field.handle_opponent_monster_zone, 5, "q1"),
        (field.handle_opponent_monster_zone, 6, "q0"),
        (field.handle_player_spell_and_trap_zone, 5, "pf"),
        (field.handle_opponent_spell_and_trap_zone, 5, "opf"),
    ]:
        q = _query(controller=1, location=card_constants.LOCATION.MONSTER_ZONE, sequence=sequence, position=1)
        delattr(q, "code")
        handler([q])
        assert expected in field.zones

    q = _query(controller=1, location=card_constants.LOCATION.EXTRA, sequence=0, position=1)
    delattr(q, "code")
    field.handle_opponent_extra_deck([q])
    assert "ox0" in field.zones


def test_append_clear_search_and_remove_card(mocker):
    from game.card import card_constants

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    query = _query(controller=1, location=card_constants.LOCATION.HAND, sequence=0, position=1)
    mine = FakeCard(1)
    mine.location = card_constants.LOCATION.HAND
    mine.sequence = 0
    opp = FakeCard(2)
    opp.controller = 1
    opp.location = card_constants.LOCATION.HAND
    opp.sequence = 0

    field.append_card_to_player_hand(mine)
    field.append_card_to_opponent_hand(opp, query)
    assert field.search_player_hand_from_left_to_right() >= 0
    assert field.search_player_hand_from_right_to_left() >= 0
    assert field.search_opponent_hand_from_left_to_right() >= 0
    assert field.search_opponent_hand_from_right_to_left() >= 0

    mock_loc = MagicMock()
    mock_loc.to_zone_key.return_value = "ph0"
    mock_loc.sequence = 0
    mocker.patch("ui.duel_field.LocationConversion.from_card_location", return_value=mock_loc)
    field.remove_card(mine)
    assert "ph0" not in field.zones

    field.append_card_to_player_extra_deck(FakeCard(3))
    field.clear_player_extra_deck()
    field.append_card_to_opponent_extra_deck(FakeCard(4), query)
    field.clear_opponent_extra_deck()
    field.append_card_to_player_graveyard(FakeCard(5))
    field.clear_player_graveyard()
    field.append_card_to_opponent_graveyard(FakeCard(6), query)
    field.clear_opponent_graveyard()
    field.append_card_to_player_banished(FakeCard(7))
    field.clear_player_banished()
    field.append_card_to_opponent_banished(FakeCard(8), query)
    field.clear_opponent_banished()


def test_remove_card_ignores_missing_tracked_zone(mocker):
    from game.card import card_constants

    field = _make_field(mocker)
    card = FakeCard(1)
    card.location = card_constants.LOCATION.HAND
    card.sequence = 0
    mock_loc = MagicMock()
    mock_loc.to_zone_key.return_value = "ph0"
    mocker.patch("ui.duel_field.LocationConversion.from_card_location", return_value=mock_loc)

    assert field.remove_card(card) is None
    assert field.zones == {}


def test_remove_card_rebuilds_opponent_and_public_zones(mocker):
    from game.card import card_constants

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)

    def location_for(client, card):
        loc = MagicMock()
        prefix = {
            (card_constants.LOCATION.HAND, 1): "oh",
            (card_constants.LOCATION.EXTRA, 0): "px",
            (card_constants.LOCATION.EXTRA, 1): "ox",
            (card_constants.LOCATION.GRAVE, 0): "pg",
            (card_constants.LOCATION.GRAVE, 1): "og",
            (card_constants.LOCATION.REMOVED, 0): "pr",
            (card_constants.LOCATION.REMOVED, 1): "or",
            (card_constants.LOCATION.MONSTER_ZONE, 0): "pm",
            (card_constants.LOCATION.MONSTER_ZONE, 1): "om",
            (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 0): "ps",
            (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 1): "os",
            (card_constants.LOCATION.FIELD_ZONE, 0): "pf",
            (card_constants.LOCATION.FIELD_ZONE, 1): "opf",
        }[(card.location, card.controller)]
        loc.to_zone_key.return_value = prefix if prefix in ("pf", "opf") else f"{prefix}{card.sequence}"
        loc.sequence = card.sequence
        return loc

    mocker.patch("ui.duel_field.LocationConversion.from_card_location", side_effect=location_for)

    query = _query(controller=1, location=card_constants.LOCATION.HAND, sequence=0, position=1)
    for location, prefix, appender in [
        (card_constants.LOCATION.HAND, "oh", field.append_card_to_opponent_hand),
        (card_constants.LOCATION.EXTRA, "ox", field.append_card_to_opponent_extra_deck),
        (card_constants.LOCATION.GRAVE, "og", field.append_card_to_opponent_graveyard),
        (card_constants.LOCATION.REMOVED, "or", field.append_card_to_opponent_banished),
    ]:
        field.zones = {}
        first = FakeCard(10)
        first.controller = 1
        first.location = location
        first.sequence = 0
        second = FakeCard(11)
        second.controller = 1
        second.location = location
        second.sequence = 1
        q1 = _query(controller=1, location=location, sequence=0, position=1)
        q2 = _query(controller=1, location=location, sequence=1, position=1)
        appender(first, q1)
        appender(second, q2)
        field.remove_card(first)
        assert f"{prefix}0" in field.zones or f"{prefix}1" in field.zones

    for location, prefix, appender in [
        (card_constants.LOCATION.EXTRA, "px", field.append_card_to_player_extra_deck),
        (card_constants.LOCATION.GRAVE, "pg", field.append_card_to_player_graveyard),
        (card_constants.LOCATION.REMOVED, "pr", field.append_card_to_player_banished),
    ]:
        field.zones = {}
        first = FakeCard(12)
        first.location = location
        first.sequence = 0
        second = FakeCard(13)
        second.location = location
        second.sequence = 1
        appender(first)
        appender(second)
        field.remove_card(first)
        assert f"{prefix}0" in field.zones or f"{prefix}1" in field.zones

    for location, controller, sequence in [
        (card_constants.LOCATION.MONSTER_ZONE, 0, 0),
        (card_constants.LOCATION.MONSTER_ZONE, 1, 0),
        (card_constants.LOCATION.MONSTER_ZONE, 0, 5),
        (card_constants.LOCATION.MONSTER_ZONE, 1, 6),
        (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 0, 0),
        (card_constants.LOCATION.SPELL_AND_TRAP_ZONE, 1, 0),
        (card_constants.LOCATION.FIELD_ZONE, 0, 0),
        (card_constants.LOCATION.FIELD_ZONE, 1, 0),
    ]:
        card = FakeCard(20)
        card.location = location
        card.controller = controller
        card.sequence = sequence
        field.remove_card(card)


def test_key_handlers_and_enter_space_paths(mocker):
    from game.card import card_constants
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    event = MagicMock()
    event.GetKeyCode.return_value = 999
    field.preemtive_key_handler = MagicMock(return_value=True)
    field.on_key_down(event)
    field.preemtive_key_handler.assert_called_once()

    field.preemtive_key_handler = None
    field.handle_enter = MagicMock()
    event.GetKeyCode.return_value = 13
    mocker.patch("ui.duel_field.wx.WXK_RETURN", 13)
    field.on_key_down(event)
    field.handle_enter.assert_called_once()

    field.handle_space = MagicMock()
    event.GetKeyCode.return_value = 32
    mocker.patch("ui.duel_field.wx.WXK_SPACE", 32)
    field.on_key_down(event)
    field.handle_space.assert_called_once()

    field.output_current_card_name = MagicMock()
    event.GetKeyCode.return_value = ord("N")
    field.on_key_down(event)
    field.output_current_card_name.assert_called_once()

    field.handle_backspace = MagicMock()
    event.GetKeyCode.return_value = 8
    mocker.patch("ui.duel_field.wx.WXK_BACK", 8)
    field.on_key_down(event)
    field.handle_backspace.assert_called_once()

    field.handle_backspace.reset_mock()
    field.browse_public_zone = MagicMock()
    field.browse_opponent_public_zones = MagicMock()
    for key, expected_prefix in [(ord("G"), "pg"), (ord("R"), "pr"), (ord("X"), "px")]:
        event.GetKeyCode.return_value = key
        field.on_key_down(event)
        assert field.browse_public_zone.call_args.args[0] == expected_prefix
    event.GetKeyCode.return_value = ord("O")
    field.on_key_down(event)
    field.browse_opponent_public_zones.assert_called_once()

    mocker.patch("ui.duel_field.duel_menu.open_chat_input")
    event.GetKeyCode.return_value = ord("M")
    field.on_key_down(event)
    from ui.duel_field import duel_menu
    duel_menu.open_chat_input.assert_called_once_with(field.client)

    card = FakeCard(9)
    field.zones = {"pm0": Zone("pm0", card)}
    field.cells[0][0] = "pm0"
    field.current_row = 0
    field.current_col = 0
    from ui.duel_field import DuelField
    DuelField.handle_space(field)
    from ui.duel_field import utils
    assert utils.output.called

    mocker.patch("ui.duel_field.duel_menu.show_duel_menu")
    DuelField.handle_backspace(field)
    duel_menu.show_duel_menu.assert_called_once_with(field.client)


def test_key_down_hand_jump_tab_and_empty_space(mocker):
    from ui.duel_field import DuelField, Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    event = MagicMock()
    event.ShiftDown.return_value = False
    mocker.patch("ui.duel_field.wx.WXK_DOWN", 40)
    mocker.patch("ui.duel_field.wx.WXK_UP", 38)
    mocker.patch("ui.duel_field.wx.WXK_TAB", 9)
    mocker.patch("ui.duel_field.wx.WXK_RETURN", 13)
    mocker.patch("ui.duel_field.wx.WXK_SPACE", 32)
    mocker.patch("ui.duel_field.wx.WXK_BACK", 8)

    event.GetKeyCode.return_value = 40
    field.current_row = field.player_spell_and_trap_row
    field.current_col = int(field.center_x)
    field.on_key_down(event)
    from ui.duel_field import utils
    assert any("No cards in hand" in str(c) for c in utils.output.call_args_list)

    field.append_card_to_player_hand(FakeCard(30))
    field.current_row = field.player_spell_and_trap_row
    field.current_col = 20
    field.on_key_down(event)
    assert field.current_col == field.search_player_hand_from_left_to_right()

    event.GetKeyCode.return_value = 38
    field.current_row = field.opponent_spell_and_trap_row
    field.current_col = int(field.center_x)
    field.on_key_down(event)
    assert any("No cards in hand" in str(c) for c in utils.output.call_args_list)

    query = _query(controller=1, location=1, sequence=0, position=1)
    field.append_card_to_opponent_hand(FakeCard(31), query)
    field.current_row = field.opponent_spell_and_trap_row
    field.current_col = 20
    field.on_key_down(event)
    assert field.current_col == field.search_opponent_hand_from_left_to_right()

    field.cells[0][0] = "pm0"
    field.zones["pm0"] = Zone("pm0", FakeCard(32))
    field.tab_order.resolve_next_tab_order.return_value = "pm0"
    event.GetKeyCode.return_value = 9
    field.on_key_down(event)
    assert (field.current_row, field.current_col) == (0, 0)

    event.ShiftDown.return_value = True
    field.tab_order.resolve_previous_tab_order.return_value = None
    field.on_key_down(event)
    assert any("No playable cards" in str(c) for c in utils.output.call_args_list)

    field.current_row = 7
    field.current_col = 7
    DuelField.handle_space(field)
    assert any("No card found" in str(c) for c in utils.output.call_args_list)

    field.cells[7][7] = "empty"
    field.zones["empty"] = Zone("empty", None)
    DuelField.handle_space(field)
    assert any("No card found" in str(c) for c in utils.output.call_args_list)

    field.zones["text"] = Zone("text", "Face down")
    field.cells[7][7] = "text"
    DuelField.handle_space(field)
    assert any("Face down" in str(c) for c in utils.output.call_args_list)

    event.GetKeyCode.return_value = ord("C")
    field.on_key_down(event)
    assert any("No chain" in str(c) for c in utils.output.call_args_list)

    event.GetKeyCode.return_value = 999
    mocker.patch("ui.duel_field.BaseUI.on_key_down")
    field.on_key_down(event)
    from ui.duel_field import BaseUI
    BaseUI.on_key_down.assert_called()


def test_handle_enter_lists_and_action_menu(mocker):
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    mocker.patch("ui.duel_field.action_menu.show_action_menu_for_zone")
    field = _make_field(mocker)
    field.show_a_card_list = MagicMock()

    field.current_row = field.player_spell_and_trap_row
    field.current_col = int(field.center_x - 3)
    field.handle_enter()
    from ui.duel_field import utils
    assert any("extra deck" in str(c).lower() for c in utils.output.call_args_list)

    field.zones["px0"] = Zone("px0", FakeCard(1))
    field.handle_enter()
    field.show_a_card_list.assert_called()

    field.current_col = int(field.center_x + 3)
    field.handle_enter()
    assert any("Player deck" in str(c) for c in utils.output.call_args_list)

    field.current_row = 0
    field.current_col = 0
    field.cells[0][0] = "pm0"
    field.zones["pm0"] = Zone("pm0", FakeCard(2))
    field.handle_enter()
    from ui.duel_field import action_menu
    action_menu.show_action_menu_for_zone.assert_called()

    field.client.is_it_my_turn = False
    action_menu.show_action_menu_for_zone.reset_mock()
    field.handle_enter()
    action_menu.show_action_menu_for_zone.assert_not_called()


def test_handle_enter_public_zone_branches(mocker):
    from ui.duel_field import Zone

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    field.show_a_card_list = MagicMock()
    from ui.duel_field import utils

    cases = [
        (field.player_monster_row, int(field.center_x + 3), "pg", "Your graveyard"),
        (field.opponent_monster_row, int(field.center_x - 3), "og", "Opponent graveyard"),
        (field.player_monster_row, int(field.center_x + 4), "pr", "Your banished cards"),
        (field.opponent_monster_row, int(field.center_x - 4), "or", "Opponent banished cards"),
        (field.opponent_spell_and_trap_row, int(field.center_x + 3), "ox", "Opponent extra deck"),
    ]
    for row, col, prefix, title in cases:
        field.zones = {}
        field.show_a_card_list.reset_mock()
        field.current_row = row
        field.current_col = col
        field.handle_enter()
        assert utils.output.called
        field.zones[f"{prefix}0"] = Zone(f"{prefix}0", FakeCard(40))
        field.handle_enter()
        field.show_a_card_list.assert_called()
        assert title in field.show_a_card_list.call_args.args[0]

    field.zones = {"ox0": Zone("ox0", "Face down card")}
    field.show_a_card_list.reset_mock()
    field.current_row = field.opponent_spell_and_trap_row
    field.current_col = int(field.center_x + 3)
    field.handle_enter()
    field.show_a_card_list.assert_not_called()


def test_show_card_list_and_time_limit(mocker):
    from game.edo import structs
    from ui.duel_field import Zone, handle_time_limit_announcement

    mocker.patch("ui.duel_field.Card", FakeCard)
    field = _make_field(mocker)
    field.client.player.chaining_cards = []
    mock_list = mocker.patch("ui.duel_field.card_list_ui.HorizontalCardList")
    mock_list.return_value.select_card.return_value = 0
    mocker.patch("ui.duel_field.action_menu.show_action_menu_for_zone")
    zone = Zone("z", FakeCard(1))
    assert field.show_a_card_list("Cards", [zone]) == zone
    field.zones = {"z0": zone}
    assert field.browse_public_zone("z", "Cards", "Empty") == zone

    mock_list.return_value.select_card.return_value = -1
    assert field.show_a_card_list("Cards", [zone]) is None
    assert field.browse_public_zone("missing", "Cards", "Empty") is None

    field.zones = {"og0": Zone("og0", FakeCard(2))}
    mock_list.return_value.select_card.return_value = 0
    assert field.browse_opponent_public_zones().card.get_name() == "Card 2"

    field.zones = {"pg0": Zone("pg0", "Empty player graveyard"), "og0": Zone("og0", "Face down card"), "or0": Zone("or0", "Face down card")}
    assert field.browse_public_zone("pg", "Cards", "Empty graveyard") is None
    assert field.browse_opponent_public_zones() is None
    assert field.show_a_card_list("Cards", ["not zone"]) is None

    chain_card = FakeCard(3)
    field.client.player.chaining_cards = [chain_card]
    field.resolve_chain = MagicMock()
    mock_list.return_value.select_card.return_value = 0
    assert field.show_a_card_list("Cards", [Zone("chain", chain_card)]).card == chain_card
    field.resolve_chain.assert_called()

    client = MagicMock()
    client.player = MagicMock()
    client.what_player_am_i = 0
    packet = structs.StocTimeLimit()
    packet.team = 0
    packet.time = 12
    handle_time_limit_announcement(client, bytes(packet), len(bytes(packet)))
    assert client.player.turn_timer == 12

    packet.team = 1
    handle_time_limit_announcement(client, bytes(packet), len(bytes(packet)))
    client.player = None
    handle_time_limit_announcement(client, bytes(packet), len(bytes(packet)))
