import struct
from unittest.mock import MagicMock

from tests.test_duel_messages_simple_more import NamedCard, _client
from tests.test_ui_flows_more import FakeMenu


def test_announce_card_search_empty_multiple_single_and_parser(mocker):
    from game.edo import structs
    from ui.duel_messages import announce_card

    client, stack = _client(mocker)
    client.read_u64 = lambda buf: struct.unpack("Q", buf.read(8))[0]

    class FakeInput:
        values = iter(["none", "multi", "single"])

        def __init__(self, *args, **kwargs):
            pass

        def show(self):
            return next(self.values)

    lang = announce_card.variables.LANGUAGE_HANDLER
    lang.get_cards_by_partial_name.side_effect = [
        {},
        {"Alpha": 111, "Beta": 222},
        {"Gamma": 333},
    ]
    mocker.patch("ui.duel_messages.announce_card.InputUI", FakeInput)
    mocker.patch("ui.duel_messages.announce_card.VerticalMenu", FakeMenu)

    announce_card.announce_card(client, 0, [])
    pushed = stack.push_ui.call_args.args[0]
    pushed.items[0][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 111))

    announce_card.announce_card(client, 0, [])
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 333))

    payload = b"\x8e" + struct.pack("B", 0) + struct.pack("B", 2) + struct.pack("Q", 1) + struct.pack("Q", 2)
    parser = mocker.patch("ui.duel_messages.announce_card.announce_card")
    announce_card.msg_announce_card(client, payload, len(payload))
    parser.assert_called_with(client, 0, [1, 2])


def test_announce_attrib_empty_multi_toggle_and_parser(mocker):
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import announce_attrib

    client, stack = _client(mocker)
    announce_attrib.variables.LANGUAGE_HANDLER.strings = {
        "system": {
            card_constants.ATTRIBUTES_OFFSET: "Earth",
            card_constants.ATTRIBUTES_OFFSET + 1: "Water",
        }
    }
    mocker.patch("ui.duel_messages.announce_attrib.VerticalMenu", FakeMenu)

    announce_attrib.show_announce_value_menu(client, "Empty", 1, [])

    announce_attrib.announce_attrib(client, 0, 2, 0b11)
    menu = stack.push_ui.call_args.args[0]
    menu.items[1][1]()
    menu.items[2][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 0b11))

    client.send.reset_mock()
    announce_attrib.show_announce_value_menu(client, "One", 0, [("Only", 4)])
    menu = stack.push_ui.call_args.args[0]
    menu.items[0][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 4))

    payload = b"\x8d" + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("I", 0b1)
    parser = mocker.patch("ui.duel_messages.announce_attrib.announce_attrib")
    announce_attrib.msg_announce_attrib(client, payload, len(payload))
    parser.assert_called_with(client, 0, 1, 1)


def test_select_option_unknown_fallback_parser_and_selection(mocker):
    from game.edo import structs
    from ui.duel_messages import select_option

    client, stack = _client(mocker)
    client.read_u64 = lambda buf: struct.unpack("Q", buf.read(8))[0]
    select_option.variables.LANGUAGE_HANDLER.strings = {"system": {5: "System Option"}}
    mocker.patch("ui.duel_messages.select_option.VerticalMenu", FakeMenu)

    card = NamedCard("Option Card")
    card.strings = []
    card.get_effect_description = MagicMock(return_value="")
    card_cls = mocker.patch("ui.duel_messages.select_option.Card", return_value=card)

    assert select_option._option_text(0, 5) == "System Option"
    assert "Unknown option 77" in select_option._option_text(123, 77)

    option = (123 << 20) | 77
    select_option.select_option(client, 0, [option])
    menu = stack.push_ui.call_args.args[0]
    assert "Option Card" in menu.items[0][0]
    menu.items[1][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 0))
    assert card_cls.call_count >= 2

    payload = b"\x0e" + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("Q", option)
    parser = mocker.patch("ui.duel_messages.select_option.select_option")
    assert select_option.msg_select_option(client, payload, len(payload)) == b""
    parser.assert_called_with(client, 0, [option])


def test_select_place_invalid_valid_multi_and_parser(mocker):
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import select_place

    client, _stack = _client(mocker)
    field = MagicMock()
    field.handle_enter = MagicMock(name="old_enter")
    old_select_place_handler = field.handle_enter
    client.get_duel_field.return_value = field
    client.flag_to_usable_cardspecs.return_value = ["pm0", "pm1"]

    loc0 = MagicMock()
    loc0.to_human_readable.return_value = "monster 0"
    loc1 = MagicMock()
    loc1.to_human_readable.return_value = "monster 1"

    def loc_from_zone(_client, key):
        return {"pm0": loc0, "pm1": loc1, "bad": MagicMock()}[key]

    mocker.patch("ui.duel_messages.select_place.LocationConversion.from_zone_key", side_effect=loc_from_zone)
    select_place.select_place(client, 0, 2, 3)
    assert field.handle_enter is not old_select_place_handler

    field.get_zone_from_current_position.return_value = None
    select_place.process_selected_zone(client, 0, 2, [loc0, loc1], field.handle_enter)
    bad_zone = MagicMock()
    bad_zone.label = "bad"
    field.get_zone_from_current_position.return_value = bad_zone
    select_place.process_selected_zone(client, 0, 2, [loc0, loc1], field.handle_enter)

    zone0 = MagicMock()
    zone0.label = "pm0"
    zone1 = MagicMock()
    zone1.label = "pm1"
    client.useful_spec_to_location.side_effect = [
        (card_constants.LOCATION.MONSTER_ZONE, 0, False),
        (card_constants.LOCATION.MONSTER_ZONE, 1, True),
    ]
    old_handler = MagicMock()
    field.get_zone_from_current_position.side_effect = [zone0, zone1]
    select_place.process_selected_zone(client, 0, 2, [loc0, loc1], old_handler)
    select_place.process_selected_zone(client, 0, 2, [loc0, loc1], old_handler)
    client.send.assert_called_with(
        structs.ClientIdType.RESPONSE,
        bytes([0, card_constants.LOCATION.MONSTER_ZONE, 0, 1, card_constants.LOCATION.MONSTER_ZONE, 1]),
    )
    assert field.handle_enter is old_handler

    parser = mocker.patch("ui.duel_messages.select_place.select_place")
    payload = b"\x18" + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("I", 9)
    select_place.msg_select_place(client, payload, len(payload))
    parser.assert_called_with(client, 0, 1, 9)


def test_update_card_error_parser_and_all_fields(mocker):
    from core import exceptions
    from game.card import card_constants
    from ui.duel_messages import update_card, update_data

    client, _stack = _client(mocker)
    client.get_card.return_value = None
    try:
        update_card.update_card(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, [])
    except exceptions.CardNotFoundException:
        pass

    card = NamedCard("Update")
    query = update_data.QueryResult()
    for field, value in {
        "code": 10,
        "alias": 11,
        "type": 12,
        "level": 4,
        "rank": 8,
        "attribute": 1,
        "race": 2,
        "attack": 3000,
        "defense": 2500,
        "base_attack": 3000,
        "base_defense": 2500,
        "reason": 7,
        "cover": 9,
        "owner": 0,
        "status": 1,
        "is_public": True,
        "lscale": 1,
        "rscale": 8,
        "link": 3,
        "link_marker": 5,
        "is_hidden": False,
        "data": b"x",
        "position": card_constants.POSITION.FACE_UP_ATTACK,
    }.items():
        setattr(query, field, value)
    mocker.patch("ui.duel_messages.update_card.Card", side_effect=lambda code: NamedCard(f"Material {code}"))
    query.overlay_cards = [101]
    update_card.apply_query_to_card(card, query)
    assert card.level == 8
    assert card.defense == 5
    assert card.xyz_materials[0].get_name() == "Material 101"

    parsed_query = MagicMock()
    parser = mocker.patch("ui.duel_messages.update_card.update_data.parse_queries", return_value=[parsed_query])
    updater = mocker.patch("ui.duel_messages.update_card.update_card")
    payload = b"\x07" + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("B", 2)
    update_card.msg_update_card(client, payload, len(payload))
    parser.assert_called()
    updater.assert_called_with(client, 0, card_constants.LOCATION.MONSTER_ZONE, 2, [parsed_query])


def test_start_parser_win_match_branches_and_effect_menu(mocker):
    from game.card import card_constants
    from game.edo import structs
    from ui.duel_messages import select_effect_yes_or_no, start, win

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.start.time.sleep")
    start_call = mocker.patch("ui.duel_messages.start.start")
    payload = b"\x04\x00" + struct.pack("I", 8000) + struct.pack("I", 7000)
    payload += struct.pack("h", 40) + struct.pack("h", 15) + struct.pack("h", 39) + struct.pack("h", 14)
    start.msg_start(client, payload, len(payload))
    start_call.assert_called_with(client, 8000, 7000, 40, 15, 39, 14)

    win.variables.LANGUAGE_HANDLER.strings = {"victory": {1: "by test"}}
    mocker.patch("ui.duel_messages.win.match_ui.score_text", return_value="1-0")
    state = {"player_wins": 2, "opponent_wins": 1}
    mocker.patch("ui.duel_messages.win.match_ui.record_duel_result", return_value=state)
    mocker.patch("ui.duel_messages.win.match_ui.is_match_over", return_value=True)
    win.win(client, 0, 1)
    state["player_wins"] = 1
    state["opponent_wins"] = 2
    win.win(client, 1, 1)

    parser = mocker.patch("ui.duel_messages.win.win")
    win.msg_win(client, b"\x05" + struct.pack("B", 1) + struct.pack("B", 1), 3)
    parser.assert_called_with(client, 1, 1)

    mocker.patch("ui.duel_messages.select_effect_yes_or_no.VerticalMenu", FakeMenu)
    card = NamedCard("Effect")
    card.get_effect_description = MagicMock(return_value="effect details")
    select_effect_yes_or_no.select_effectyn(client, 0, card, 123)
    menu = stack.push_ui.call_args.args[0]
    menu.items[1][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 1))
    select_effect_yes_or_no.select_effectyn(client, 0, card, 123)
    menu = stack.push_ui.call_args.args[0]
    menu.items[2][1]()
    client.send.assert_called_with(structs.ClientIdType.RESPONSE, struct.pack("I", 0))

    parsed = NamedCard("Parsed Effect")
    parsed.get_effect_description = MagicMock(return_value="")
    card_cls = mocker.patch("ui.duel_messages.select_effect_yes_or_no.Card", return_value=parsed)
    client.read_u64 = lambda buf: struct.unpack("Q", buf.read(8))[0]
    data = b"\x0c" + struct.pack("B", 0) + struct.pack("I", 123)
    data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    data += struct.pack("Q", 456)
    select_effect_yes_or_no.msg_select_effectyn(client, data, len(data))
    card_cls.assert_called_with(123)


def test_remaining_small_duel_message_branches(mocker):
    from game.card import card_constants
    from ui.duel_messages import announce_attrib, attack, become_target, card_hint, deck_top, idle, select_card, shuffle_other, summoning, update_card, update_data, win

    client, stack = _client(mocker)

    announce_attrib._toggle_value(client, MagicMock(), [1], 2, "Earth", 1)
    announce_attrib._toggle_value(client, MagicMock(), [1, 2], 2, "Fire", 4)
    announce_attrib._finish_multi_select(client, [1], 2)

    mocker.patch("ui.duel_messages.attack.Card", NamedCard)
    attacker = NamedCard("Attacker")
    target = NamedCard("Target")
    client.get_card.side_effect = [attacker, target]
    attack.attack(
        client,
        0,
        card_constants.LOCATION.MONSTER_ZONE,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        1,
        card_constants.LOCATION.MONSTER_ZONE,
        1,
        card_constants.POSITION.FACE_UP_ATTACK,
    )
    client.get_card.side_effect = [attacker, target]
    attack.attack(
        client,
        1,
        card_constants.LOCATION.MONSTER_ZONE,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        0,
        card_constants.LOCATION.MONSTER_ZONE,
        1,
        card_constants.POSITION.FACE_UP_ATTACK,
    )
    client.get_card.side_effect = [attacker, None]
    attack.attack(
        client,
        0,
        card_constants.LOCATION.MONSTER_ZONE,
        0,
        card_constants.POSITION.FACE_UP_ATTACK,
        1,
        card_constants.LOCATION.MONSTER_ZONE,
        1,
        card_constants.POSITION.FACE_UP_ATTACK,
    )
    client.get_card.side_effect = [attacker]
    attack.attack(client, 1, card_constants.LOCATION.MONSTER_ZONE, 0, 0, 0, 0, 0, 0)
    parser = mocker.patch("ui.duel_messages.attack.attack")
    payload = b"\x6e"
    payload += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    payload += struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 1) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    attack.msg_attack(client, payload, len(payload))
    parser.assert_called()

    client.get_card.side_effect = None
    client.get_card.return_value = hinted = NamedCard("Targeted")
    target_parser = mocker.patch("ui.duel_messages.become_target.become_target")
    target_payload = b"\x53" + struct.pack("I", 1)
    target_payload += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    become_target.msg_become_target(client, target_payload, len(target_payload))
    target_parser.assert_called_with(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK)

    card_hint.variables.LANGUAGE_HANDLER.strings = {
        "system": {
            card_constants.RACES_OFFSET: "Warrior",
            card_constants.ATTRIBUTES_OFFSET: "Earth",
        }
    }
    hinted = NamedCard("Hinted")
    card_hint.card_hint(client, hinted, 3, 1)
    card_hint.card_hint(client, hinted, 4, 1)
    client.get_card.side_effect = None
    client.unpack_location.return_value = (0, card_constants.LOCATION.MONSTER_ZONE, 0, 0)
    client.get_card.return_value = hinted
    hint_payload = b"\xa0" + struct.pack("I", 123) + struct.pack("B", 3) + struct.pack("I", 1)
    assert card_hint.msg_card_hint(client, hint_payload, len(hint_payload)) == b""
    client.get_card.return_value = None
    assert card_hint.msg_card_hint(client, hint_payload, len(hint_payload)) == b""

    skipped = update_data.QueryResult()
    skipped.fields = {"flags": card_constants.QUERY(0)}
    skipped.onfield_skipped = True
    assert update_card.apply_query_to_card(NamedCard("Skipped"), skipped).get_name() == "Skipped"

    face_down = NamedCard("Hidden")
    face_down.code = 0
    loc = MagicMock()
    loc.to_human_readable.return_value = "hidden zone"
    mocker.patch("ui.duel_messages.select_card.LocationConversion.from_card_location", return_value=loc)
    select_menu = mocker.patch("ui.duel_messages.select_card.show_menu_with_presentable_cards")
    select_card.select_card(client, 0, 0, 1, 1, [face_down])
    assert "Face down card" in select_menu.call_args.args[2][0]

    client.player.summonable = [attacker]
    client.player.special_summonable = []
    client.player.repositionable = []
    client.player.monster_settable = []
    client.player.spell_settable = []
    client.player.activatable = []
    field = MagicMock()
    field.zones = {"empty": MagicMock(card=object()), "monster": MagicMock(card=attacker)}
    client.get_duel_field.return_value = field
    mocker.patch("ui.duel_messages.idle.Card", NamedCard)
    idle.idle(client, 0)
    field.tab_order.set_tabable_items.assert_called_with(["monster"])

    mocker.patch("ui.duel_messages.win.match_ui.record_duel_result", return_value={"player_wins": 1, "opponent_wins": 0})
    mocker.patch("ui.duel_messages.win.match_ui.score_text", return_value="1-0")
    mocker.patch("ui.duel_messages.win.match_ui.is_match_over", return_value=False)
    win._announce_match_result(client, 0)

    deck_cls = mocker.patch("ui.duel_messages.deck_top.Card", side_effect=lambda code: NamedCard(f"Deck {code}"))
    deck_payload = b"\x26" + struct.pack("B", 0) + struct.pack("I", 0)
    deck_payload += struct.pack("I", 123 | 0x80000000) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    deck_top.msg_decktop(client, deck_payload, len(deck_payload))
    deck_cls.assert_called_with(123)

    shuffle_other.msg_shuffle_extra_deck(client, b"\x27" + struct.pack("B", 1) + struct.pack("I", 1) + struct.pack("I", 7), 10)

    summoned = summoning.msg_summoned(client, b"\x3drest", 5)
    assert summoned == b"rest"
    special = mocker.patch("ui.duel_messages.summoning.msg_summoning")
    summoning.msg_summoning_special(client, b"\x3edata", 5)
    special.assert_called_with(client, b"\x3edata", 5, special=True)

    from core import utils
    assert any("Unselected Earth" in call.args[0] for call in utils.output.call_args_list)
    assert any("already selected" in call.args[0] for call in utils.output.call_args_list)
    assert any("Prepare to side deck" in call.args[0] for call in utils.output.call_args_list)
    stack.play_duel_sound_effect.assert_any_call("attack")
