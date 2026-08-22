import struct
from unittest.mock import MagicMock

from tests.test_duel_messages_simple_more import NamedCard, _client
from tests.test_ui_flows_more import FakeMenu


class FakeCheckbox:
    checked = True

    def __init__(self, *args, **kwargs):
        pass

    def IsChecked(self):
        return self.checked


def test_deck_top_confirm_and_single_reveal(mocker):
    from game.card import card_constants
    from ui.duel_messages import deck_top

    client, _stack = _client(mocker)
    card_cls = mocker.patch("ui.duel_messages.deck_top.Card", side_effect=lambda code: NamedCard(f"Card {code}"))
    deck_top.decktop(client, 0, NamedCard("Mine"))
    deck_top.decktop(client, 1, NamedCard("Opp"))
    deck_top.confirm_decktop(client, 0, [NamedCard("A"), NamedCard("B")])
    deck_top.confirm_decktop(client, 1, [NamedCard("C")])
    from core import utils
    assert utils.output.call_count >= 6

    data = b"\x1e" + struct.pack("B", 0) + struct.pack("I", 1)
    data += struct.pack("I", 123 | 0x80000000) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.DECK) + struct.pack("I", 0)
    deck_top.msg_confirm_decktop(client, data, len(data))
    data = b"\x26" + struct.pack("B", 0) + struct.pack("I", 0) + struct.pack("I", 456) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    deck_top.msg_decktop(client, data, len(data))
    assert card_cls.call_count >= 2


def test_draw_face_down_and_sound_helper(mocker):
    from game.card import card_constants
    from ui.duel_messages import draw

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.draw.threading.Thread")
    card_cls = mocker.patch("ui.duel_messages.draw.Card")
    card_cls.side_effect = [Exception("ignored")]
    face_down = NamedCard("")
    face_down.get_name = MagicMock(return_value="")
    draw.draw(client, 0, [face_down])

    mocker.patch("ui.duel_messages.draw.time.sleep")
    draw._play_draw_sound_effect(2)
    assert stack.play_random_duel_sound_effect_in_directory.call_count == 2


def test_draw_syncs_hand_zones(mocker):
    from ui.duel_messages import draw

    client, _stack = _client(mocker)
    field = MagicMock()
    player_hand = []
    opponent_hand = []
    field.get_subset_of_zones.side_effect = lambda prefix: {f"{prefix}{i}": card for i, card in enumerate(player_hand if prefix == "ph" else opponent_hand)}
    field.append_card_to_player_hand.side_effect = lambda card: player_hand.append(card)
    field.append_card_to_opponent_hand.side_effect = lambda card, query: opponent_hand.append(card)
    client.get_duel_field.return_value = field

    first = NamedCard("First")
    second = NamedCard("Second")
    draw.draw(client, 0, [first, second])
    draw.draw(client, 1, [None])

    assert player_hand == [first, second]
    assert first.sequence == 0
    assert second.sequence == 1
    assert opponent_hand == ["Face down card"]


def test_update_card_applies_accessibility_fields(mocker):
    from game.card import card_constants
    from ui.duel_field import DuelField, Zone
    from ui.duel_messages import update_card, update_data

    card = NamedCard("XYZ Pendulum")
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.XYZ | card_constants.TYPE.PENDULUM
    card.location = card_constants.LOCATION.MONSTER_ZONE
    card.position = card_constants.POSITION.FACE_UP_ATTACK
    card.get_link_markers = MagicMock(return_value="bottom")
    client, _stack = _client(mocker)
    client.get_card.return_value = card
    material_cls = mocker.patch("ui.duel_messages.update_card.Card", side_effect=lambda code: NamedCard(f"Material {code}"))

    query = update_data.QueryResult()
    query.onfield_skipped = False
    query.overlay_cards = [11, 22]
    query.lscale = 3
    query.rscale = 8
    query.link_marker = 1
    update_card.update_card(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, [query])

    assert [material.get_name() for material in card.xyz_materials] == ["Material 11", "Material 22"]
    assert card.lscale == 3
    assert card.rscale == 8
    assert card.link_marker == 1
    assert material_cls.call_count == 2

    mocker.patch("ui.duel_field.Card", NamedCard)
    client.player.activatable = []
    client.player.chaining_cards = []
    client.player.attackable = []
    client.player.summonable = []
    client.player.special_summonable = []
    client.player.repositionable = []
    client.player.monster_settable = []
    client.player.spell_settable = []
    field = DuelField.__new__(DuelField)
    field.client = client
    field.zones = {"pm0": Zone("pm0", card)}
    info = field.get_card_information_to_show_when_card_is_selected(field.zones["pm0"])
    assert "XYZ materials (2): Material 11, Material 22" in info
    assert "Pendulum scale: 3/8" in info
    assert "Link Markers: bottom" in info


def test_sort_card_full_flow(mocker):
    from game.edo import structs
    from ui.duel_messages import sort_card

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.sort_card.VerticalMenu", FakeMenu)
    cards = [NamedCard("A"), NamedCard("B"), NamedCard("C")]
    sort_card.sort_card(client, 0, cards)
    pushed = stack.push_ui.call_args.args[0]
    assert pushed.items[1][0] == "A"
    pushed.items[2][1]()
    next_menu = stack.push_ui.call_args.args[0]
    next_menu.items[1][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1) + b"\x01\x00\x02")

    stack.pop_ui.reset_mock()
    sort_card.finish_sort(client, [2, 1, 0])
    stack.pop_ui.assert_called()

    card_cls = mocker.patch("ui.duel_messages.sort_card.Card", side_effect=lambda code: NamedCard(f"Sort {code}"))
    data = b"\x17" + struct.pack("B", 0) + struct.pack("I", 2)
    data += struct.pack("I", 10) + struct.pack("B", 0) + struct.pack("B", 4) + struct.pack("I", 0)
    data += struct.pack("I", 20) + struct.pack("B", 0) + struct.pack("B", 4) + struct.pack("I", 1)
    sort_card.msg_sort_card(client, data, len(data))
    assert card_cls.call_count == 2


def test_select_sum_validation_and_finish(mocker):
    from game.edo import structs
    from ui.duel_messages import select_sum

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.select_sum.VerticalMenu", FakeMenu)
    mocker.patch("ui.duel_messages.select_sum.wx.CheckBox", FakeCheckbox)
    must = NamedCard("Must")
    must.param = 4
    optional = NamedCard("Optional")
    optional.param = 3
    select_sum.select_sum(client, 0, 0, 7, 1, 2, [must], [optional])
    menu = stack.push_ui.call_args.args[0]
    assert any("exactly 7" in item[0] for item in menu.items)

    checked = FakeCheckbox()
    menu.cells = [[checked]]
    select_sum.finish_sum_selection(client, menu, [must], [optional], 8, 0)
    from core import utils
    assert any("exactly" in str(c) for c in utils.output.call_args_list)
    select_sum.finish_sum_selection(client, menu, [must], [optional], 7, 0)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1) + struct.pack("I", 2) + struct.pack("H", 0) + struct.pack("H", 1))

    client.send.reset_mock()
    select_sum.finish_sum_selection(client, menu, [], [optional], 10, 1)
    assert any("at least" in str(c) for c in utils.output.call_args_list)

    card_cls = mocker.patch("ui.duel_messages.select_sum.Card", side_effect=lambda code: NamedCard(f"Sum {code}"))
    payload = b"\x16" + struct.pack("B", 0) + struct.pack("B", 1)
    payload += struct.pack("I", 7) + struct.pack("I", 1) + struct.pack("I", 3)
    payload += struct.pack("I", 1)
    payload += struct.pack("I", 111) + struct.pack("B", 0) + struct.pack("B", 4) + struct.pack("I", 0) + struct.pack("I", 4)
    payload += struct.pack("I", 1)
    payload += struct.pack("I", 222) + struct.pack("B", 0) + struct.pack("B", 4) + struct.pack("I", 1) + struct.pack("I", 3)
    select_sum.msg_select_sum(client, payload, len(payload))
    assert card_cls.call_count >= 2


def test_select_counter_validation_finish_and_parser(mocker):
    from game.edo import structs
    from ui.duel_messages import select_counter

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.select_counter.VerticalMenu", FakeMenu)

    class FakeSlider:
        def __init__(self, value=0):
            self.value = value
            self.range = None

        def SetRange(self, start, end):
            self.range = (start, end)

        def SetValue(self, value):
            self.value = value

        def GetValue(self):
            return self.value

    sliders = [FakeSlider(), FakeSlider()]
    mocker.patch("ui.duel_messages.select_counter.wx.Slider", FakeSlider)
    card1 = NamedCard("Counter A")
    card1.counter_count = 3
    card2 = NamedCard("Counter B")
    card2.counter_count = 2
    select_counter.select_counter(client, 0, 1, 3, [card1, card2])
    menu = stack.push_ui.call_args.args[0]
    assert any("Remove 3" in item[0] for item in menu.items)

    menu.cells = [[sliders[0]], [sliders[1]]]
    sliders[0].value = 1
    sliders[1].value = 1
    select_counter.finish_counter_selection(client, menu, [card1, card2], 3)
    from core import utils
    assert any("exactly 3" in str(c) for c in utils.output.call_args_list)

    sliders[0].value = 1
    sliders[1].value = 2
    select_counter.finish_counter_selection(client, menu, [card1, card2], 3)
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1) + struct.pack("H", 1) + struct.pack("H", 2))

    card_cls = mocker.patch("ui.duel_messages.select_counter.Card", side_effect=lambda code: NamedCard(f"Counter {code}"))
    payload = b"\x11" + struct.pack("B", 0) + struct.pack("H", 5) + struct.pack("H", 2) + struct.pack("I", 1)
    payload += struct.pack("I", 333) + struct.pack("B", 0) + struct.pack("B", 4) + struct.pack("B", 0) + struct.pack("H", 4)
    select_counter.msg_select_counter(client, payload, len(payload))
    assert card_cls.called


def test_select_chain_player_flow_parser_and_keyboard(mocker):
    import wx
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import select_chain

    client, stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field
    zone = MagicMock()
    field.get_zone_from_current_position.return_value = zone
    field.resolve_chain.return_value = True
    loc = MagicMock()
    loc.to_zone_key.return_value = "pm0"
    mocker.patch("ui.duel_messages.select_chain.LocationConversion.from_card_location", return_value=loc)

    card = NamedCard("Chainable")
    card.get_effect_description = MagicMock(return_value="effect text")
    select_chain.select_chain(client, 0, 1, 0, 0, [(0, card, 123)])

    assert client.player.chaining_cards == [card]
    field.tab_order.set_tabable_items.assert_called_with(["pm0"])
    stack.play_duel_sound_effect.assert_called_with("chain")
    assert field.preemtive_key_handler is not None

    event = MagicMock()
    event.GetKeyCode.return_value = wx.WXK_ESCAPE
    assert field.preemtive_key_handler(client, event) is True
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("i", -1))
    assert field.preemtive_key_handler is None

    select_chain.select_chain(client, 0, 1, 0, 1, [(0, card, 123)])
    forced_handler = field.preemtive_key_handler
    event.GetKeyCode.return_value = wx.WXK_ESCAPE
    assert forced_handler(client, event, ) is None
    event.GetKeyCode.return_value = wx.WXK_RETURN
    assert forced_handler(client, event) is True
    field.resolve_chain.assert_called_with(zone)

    parsed = NamedCard("Parsed Chain")
    parsed.get_effect_description = MagicMock(return_value="parsed effect")
    card_cls = mocker.patch("ui.duel_messages.select_chain.Card", return_value=parsed)
    payload = b"\x10" + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("B", 0)
    payload += struct.pack("I", 1) + struct.pack("I", 2) + struct.pack("I", 1)
    payload += struct.pack("I", 444)
    payload += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    payload += struct.pack("Q", 9) + struct.pack("B", 3)
    select_chain.msg_select_chain(client, payload, len(payload))
    card_cls.assert_called_with(444)


def test_chaining_target_hint_random_remove_shuffle_swap(mocker):
    from game.card import card_constants
    from ui.duel_messages import become_target, card_hint, chained, chaining, hint, move, position_change, random_selected, remove_cards, shuffle_other, swap

    client, stack = _client(mocker)
    card = NamedCard("Effect")
    card.get_effect_description = MagicMock(return_value="description")
    card.controller = 0
    chaining.chaining(client, card, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 1, 2)
    card.controller = 1
    card.get_effect_description = MagicMock(return_value="")
    chaining.chaining(client, card, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 1, 2)

    parsed_card = NamedCard("Parsed Effect")
    parsed_card.get_effect_description = MagicMock(return_value="parsed")
    card_cls = mocker.patch("ui.duel_messages.chaining.Card", return_value=parsed_card)
    data = b"\x46" + struct.pack("I", 123)
    data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 1)
    data += struct.pack("Q", 9) + struct.pack("I", 2)
    chaining.msg_chaining(client, data, len(data))
    card_cls.assert_called_with(123)

    chained.msg_chained(client, b"\x47\x02rest", 6)
    chained.msg_chain_solved(client, b"\x49\x01rest", 6)
    chained.msg_chain_negated(client, b"\x4b\x03rest", 6)
    chained.msg_chain_disabled(client, b"\x4c\x04rest", 6)
    assert chained.msg_chain_end(client, b"\x4a", 1) is None

    client.get_card.return_value = card
    become_target.become_target(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK)
    card.controller = 1
    card.position = card_constants.POSITION.FACE_DOWN
    loc = MagicMock()
    loc.to_human_readable.return_value = "opponent monster"
    mocker.patch("ui.duel_messages.become_target.LocationConversion.from_card_location", return_value=loc)
    become_target.become_target(client, 1, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_DOWN)
    client.get_card.return_value = None
    loc_cls = mocker.patch("ui.duel_messages.become_target.LocationConversion")
    loc_cls.return_value.to_zone_key.return_value = "om0"
    client.get_duel_field.return_value.zones.keys.return_value = []
    try:
        become_target.become_target(client, 1, card_constants.LOCATION.MONSTER_ZONE, 0, 0)
    except ValueError:
        pass

    lang = MagicMock()
    lang._ = lambda s: s
    lang.strings = {"system": {card_constants.RACES_OFFSET: "Race", card_constants.ATTRIBUTES_OFFSET: "Attr"}}
    mocker.patch("ui.duel_messages.card_hint.variables.LANGUAGE_HANDLER", lang)
    card_hint.card_hint(client, NamedCard("Hint"), 3, 1)
    card_hint.card_hint(client, NamedCard("Hint"), 4, 1)
    card_hint.card_hint(client, NamedCard("Hint"), 99, 1)

    hint.variables.LANGUAGE_HANDLER.strings = {"system": {1512: "Number %d"}}
    hint.hint(client, hint.HINT.MESSAGE, 0, "Direct message")
    hint.hint(client, hint.HINT.NUMBER, 0, 5)
    hint.hint(client, hint.HINT.EVENT, 0, 99)
    hint.msg_hint(client, b"\x02" + struct.pack("B", int(hint.HINT.NUMBER)) + struct.pack("B", 0) + struct.pack("Q", 7), 11)

    loc1 = MagicMock()
    loc1.to_human_readable.return_value = "Your deck 1"
    random_selected.random_selected(client, 0, [loc1])
    random_selected.random_selected(client, 1, [loc1])
    loc_cls = mocker.patch("ui.duel_messages.random_selected.LocationConversion", return_value=loc1)
    random_data = b"\x51" + struct.pack("B", 0) + struct.pack("I", 1)
    random_data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.DECK) + struct.pack("I", 0) + struct.pack("I", 0)
    random_selected.msg_random_selected(client, random_data, len(random_data))
    loc_cls.assert_called()

    remove_cards.remove_cards(client, [(0, card_constants.LOCATION.DECK, 0, 0)])
    mocker.patch("ui.duel_messages.remove_cards.LocationConversion", return_value=loc1)
    remove_data = b"\xbe" + struct.pack("I", 1)
    remove_data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.DECK) + struct.pack("I", 0) + struct.pack("I", 0)
    remove_cards.msg_remove_cards(client, remove_data, len(remove_data))

    shuffle_other.shuffle_others(client, 0, card_constants.LOCATION.HAND, 2, [1, 2])
    shuffle_other.shuffle_others(client, 1, card_constants.LOCATION.EXTRA, 2, [1, 2])
    stack.play_duel_sound_effect.assert_any_call("shuffle")

    card1 = NamedCard("Swap1")
    card1.controller = 1
    card2 = NamedCard("Swap2")
    card2.controller = 1
    mocker.patch("ui.duel_messages.swap.LocationConversion.from_card_location", return_value=loc1)
    swap.swap(client, card1, card2)
    card2.controller = 0
    swap.swap(client, card1, card2)
    swap_card_cls = mocker.patch("ui.duel_messages.swap.Card", side_effect=lambda code: NamedCard(f"Swap {code}"))
    swap_data = b"\x37" + struct.pack("I", 10)
    swap_data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", 1)
    swap_data += struct.pack("I", 20)
    swap_data += struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 1) + struct.pack("I", 1)
    assert swap.msg_swap(client, swap_data, len(swap_data)) == b""
    assert swap_card_cls.call_count == 2

    pos_card = NamedCard("Position")
    pos_card.controller = 1
    pos_card.position = card_constants.POSITION.FACE_UP_DEFENSE
    position_change.position_change(client, pos_card, card_constants.POSITION.FACE_DOWN_ATTACK)
    pos_cls = mocker.patch("ui.duel_messages.position_change.Card", return_value=NamedCard("Parsed Position"))
    pos_data = b"\x35" + struct.pack("I", 123) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE)
    pos_data += struct.pack("B", 0) + struct.pack("B", card_constants.POSITION.FACE_DOWN_DEFENSE) + struct.pack("B", card_constants.POSITION.FACE_UP_ATTACK)
    position_change.msg_pos_change(client, pos_data, len(pos_data))
    pos_cls.assert_called_with(123)

    old = NamedCard("Moved")
    old.controller = 1
    old.location = card_constants.LOCATION.GRAVE
    old.get_name = MagicMock(return_value="Moved")
    new = NamedCard("Moved")
    new.controller = 1
    new.location = card_constants.LOCATION.MONSTER_ZONE
    loc1.to_human_readable.return_value = "field"
    mocker.patch("ui.duel_messages.move.LocationConversion.from_card_location", return_value=loc1)
    assert "opponent" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))
    old.location = card_constants.LOCATION.REMOVED
    assert "banished" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))
    new.location = card_constants.LOCATION.HAND
    assert "opponent" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))
    new.location = card_constants.LOCATION.DECK
    assert "deck" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))
    new.location = card_constants.LOCATION.EXTRA
    assert "extra" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))


def test_move_parser_and_remaining_opponent_messages(mocker):
    from game.card import card_constants
    from ui.duel_messages import move

    client, _stack = _client(mocker)
    field = MagicMock()
    client.get_duel_field.return_value = field

    loc = MagicMock()
    loc.to_human_readable.return_value = "opponent field"
    mocker.patch("ui.duel_messages.move.LocationConversion.from_card_location", return_value=loc)

    first = NamedCard("Parsed Move")
    second = NamedCard("Parsed Move")
    card_cls = mocker.patch("ui.duel_messages.move.Card", side_effect=[first, second])
    payload = b"\x32" + struct.pack("I", 123)
    payload += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.HAND) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP)
    payload += struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.GRAVE) + struct.pack("I", 1) + struct.pack("I", card_constants.POSITION.FACE_UP)
    payload += struct.pack("I", card_constants.REASON.DISCARD)
    move.msg_move(client, payload, len(payload))
    assert card_cls.call_count == 2
    field.remove_card.assert_called_with(first)
    field.append_card_to_opponent_graveyard.assert_called_once()

    old = NamedCard("Moved")
    old.controller = 1
    old.get_name = MagicMock(return_value="Moved")
    new = NamedCard("Moved")
    new.controller = 1
    new.get_name = MagicMock(return_value="Moved")

    cases = [
        (card_constants.LOCATION.MONSTER_ZONE, card_constants.LOCATION.GRAVE, card_constants.REASON.DESTROY, "destroyed"),
        (card_constants.LOCATION.MONSTER_ZONE, card_constants.LOCATION.GRAVE, card_constants.REASON.RELEASE | card_constants.REASON.SUMMON, "tributed"),
        (card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE, card_constants.LOCATION.GRAVE, card_constants.REASON(0), "overlay"),
        (card_constants.LOCATION.HAND, card_constants.LOCATION.GRAVE, card_constants.REASON(0), "graveyard"),
        (card_constants.LOCATION.HAND, card_constants.LOCATION.REMOVED, card_constants.REASON(0), "banished"),
        (card_constants.LOCATION.DECK, card_constants.LOCATION.SPELL_AND_TRAP_ZONE, card_constants.REASON(0), "deck"),
    ]
    for old_location, new_location, reason, expected in cases:
        old.location = old_location
        new.location = new_location
        new.position = card_constants.POSITION.FACE_UP_ATTACK
        assert expected in move.get_message_to_announce(client, old, new, reason)

    old.location = card_constants.LOCATION.MONSTER_ZONE
    old.controller = 1
    new.location = card_constants.LOCATION.MONSTER_ZONE
    new.controller = 0
    assert "switched control" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))

    old.controller = 1
    new.controller = 1
    old.sequence = 0
    new.sequence = 2
    assert "changed column" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))

    old.controller = 1
    new.controller = 1
    new.location = card_constants.LOCATION.OVERLAY | card_constants.LOCATION.MONSTER_ZONE
    target = NamedCard("Target XYZ")
    client.get_card.return_value = target
    assert "Target XYZ" in move.get_message_to_announce(client, old, new, card_constants.REASON(0))


def test_draw_parser_handles_unknown_card_and_battle_non_link_defender(mocker):
    from core import exceptions
    from game.card import card_constants
    from ui.duel_messages import damage_step_battle, draw

    client, _stack = _client(mocker)
    mocker.patch("ui.duel_messages.draw.Card", side_effect=exceptions.CardNotFoundException("missing"))
    payload = b"\x5a" + struct.pack("B", 0) + struct.pack("I", 1)
    payload += struct.pack("I", 999999) + struct.pack("I", card_constants.POSITION.FACE_DOWN)
    draw.msg_draw(client, payload, len(payload))

    attacker = NamedCard("Attacker", card_type=card_constants.TYPE.MONSTER)
    defender = NamedCard("Defender", card_type=card_constants.TYPE.MONSTER)
    client.get_card.side_effect = [attacker, defender]
    damage_step_battle.damage_step_battle(
        client,
        0,
        card_constants.LOCATION.MONSTER_ZONE,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        1800,
        1200,
        0,
        1,
        card_constants.LOCATION.MONSTER_ZONE,
        1,
        card_constants.POSITION.FACE_UP_ATTACK,
        1500,
        1000,
        0,
    )

    from core import utils
    assert any("Defender (1500/1000)" in call.args[0] for call in utils.output.call_args_list)
