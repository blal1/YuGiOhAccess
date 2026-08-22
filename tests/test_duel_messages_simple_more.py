import struct
from types import SimpleNamespace
from unittest.mock import MagicMock


class NamedCard:
    def __init__(self, name="Card", attack=1000, defense=1000, card_type=0):
        self.code = 1
        self.name = name
        self.attack = attack
        self.defense = defense
        self.type = card_type
        self.controller = 0
        self.location = 0
        self.sequence = 0
        self.position = 0

    def get_name(self):
        return self.name

    def get_position(self):
        return "face-down"

    def set_location_and_position_info(self, controller, location, sequence, position):
        self.controller = controller
        self.location = location
        self.sequence = sequence
        self.position = position


def _client(mocker):
    client = MagicMock()
    client.what_player_am_i = 0
    client.read_u8 = lambda buf: struct.unpack("B", buf.read(1))[0]
    client.read_u16 = lambda buf: struct.unpack("h", buf.read(2))[0]
    client.read_u32 = lambda buf: struct.unpack("I", buf.read(4))[0]
    client.read_location = lambda buf: (
        client.read_u8(buf),
        client.read_u8(buf),
        client.read_u32(buf),
        client.read_u32(buf),
    )
    lang = MagicMock()
    lang._ = lambda s: s
    lang.strings = {"victory": {0: "reason"}}
    mocker.patch("core.variables.LANGUAGE_HANDLER", lang)
    mocker.patch("core.utils.output")
    stack = MagicMock()
    stack.sound_effects_audio_manager.sources = {}
    mocker.patch("core.utils.get_ui_stack", return_value=stack)
    return client, stack


def test_attack_direct_and_targeted(mocker):
    from game.card import card_constants
    from ui.duel_messages import attack

    client, stack = _client(mocker)
    attacker = NamedCard("Attacker")
    target = NamedCard("Target")
    client.get_card.side_effect = [attacker, attacker, target]

    attack.attack(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 0, 0, 0, 0, 0)
    attack.attack(client, 1, card_constants.LOCATION.MONSTER_ZONE, 0, 0, 0, card_constants.LOCATION.MONSTER_ZONE, 1, 0)
    assert stack.play_duel_sound_effect.call_count == 2
    from core import utils
    assert utils.output.call_count == 2

    client.get_card.return_value = None
    client.get_card.side_effect = None
    attack.attack(client, 0, card_constants.LOCATION.MONSTER_ZONE, 0, 0, 0, 0, 0, 0)


def test_draw_branches_and_message_parser(mocker):
    from game.card import card_constants
    from ui.duel_messages import draw

    client, stack = _client(mocker)
    mocker.patch("ui.duel_messages.draw.threading.Thread")
    draw.draw(client, 0, [None, None])
    face_down = MagicMock()
    face_down.get_name.return_value = ""
    draw.draw(client, 1, [face_down])
    card = NamedCard("Drawn")
    draw.draw(client, 0, [card, None])
    from core import utils
    assert utils.output.call_count >= 4

    card_cls = mocker.patch("ui.duel_messages.draw.Card", return_value=NamedCard("Parsed"))
    data = b"\x5a" + struct.pack("B", 0) + struct.pack("I", 1) + struct.pack("I", 123) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    draw.msg_draw(client, data, len(data))
    card_cls.assert_called_with(123)


def test_start_phase_win_and_lp_messages(mocker, tmp_path):
    from game.card import card_constants
    from game.player import Player
    from ui.duel_messages import lpupdate, pay_cost, phase, recover, start, win

    client, stack = _client(mocker)
    music_dir = tmp_path / "sounds" / "music" / "duel_standard"
    music_dir.mkdir(parents=True)
    (music_dir / "track.ogg").write_bytes(b"")
    for folder in ("duel_winning", "duel_losing"):
        path = tmp_path / "sounds" / "music" / folder
        path.mkdir(parents=True)
        (path / "track.ogg").write_bytes(b"")
    mocker.patch("game.player.variables.LOCAL_DATA_DIR", tmp_path)
    mocker.patch("game.player.random.choice", return_value=music_dir / "track.ogg")
    mocker.patch("ui.duel_messages.start.time.sleep")
    mocker.patch("ui.duel_messages.start.duel_field.DuelField", return_value="field")
    field = start.start.__wrapped__(client, 8000, 8000, 40, 15, 40, 15)
    assert field == "field"
    assert isinstance(client.player, Player)

    client.player = Player(8000, 8000)
    recover.recover(client, 0, 500)
    recover.recover(client, 1, 400)
    pay_cost.pay_lpcost(client, 0, 200)
    pay_cost.pay_lpcost(client, 1, 300)
    assert client.player.lifepoints == 8300
    assert client.player.opponent_lifepoints == 8100

    lpupdate.lpupdate(client, 0, 7000)
    lpupdate.lpupdate(client, 1, 0)
    stack.play_duel_sound_effect.assert_any_call("lpend")
    stack.play_duel_sound_effect.assert_any_call("lpzero")

    client.player = MagicMock(lifepoints=7000, opponent_lifepoints=0)
    client.is_it_my_turn = True
    mocker.patch("ui.duel_messages.phase.utils.get_discord_presence_manager", return_value=MagicMock())
    for phase_id in (2, 4, 8, 0x200, 1234):
        phase.phase(client, phase_id)
    assert client.current_phase == 1234
    phase.msg_new_phase(client, b"\x29" + struct.pack("H", 4), 3)
    assert client.current_phase == 4

    client.what_player_am_i = 0
    win.win(client, 2, 0)
    win.win(client, 0, 0)
    assert client.player is None
    assert client.turn_count == 0


def test_position_change_and_summoning(mocker):
    from game.card import card_constants
    from ui.duel_messages import position_change, summoning

    client, stack = _client(mocker)
    card = NamedCard("Monster")
    card.controller = 0
    for prev, new, sound in [
        (card_constants.POSITION.FACE_DOWN, card_constants.POSITION.FACE_UP, "switch_flip"),
        (card_constants.POSITION.FACE_UP, card_constants.POSITION.FACE_DOWN, "switch_facedown"),
        (card_constants.POSITION.FACE_UP_DEFENSE, card_constants.POSITION.FACE_UP_ATTACK, "switch_attack"),
        (card_constants.POSITION.FACE_UP_ATTACK, card_constants.POSITION.FACE_UP_DEFENSE, "switch_defense"),
    ]:
        card.position = new
        position_change.position_change(client, card, prev)
        stack.play_duel_sound_effect.assert_any_call(sound)

    summoning.summoning(client, card, 0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK)
    summoning.summoning(client, card, 1, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK, special=True)
    card.type = card_constants.TYPE.LINK
    summoning.summoning(client, card, 0, card_constants.LOCATION.MONSTER_ZONE, 0, card_constants.POSITION.FACE_UP_ATTACK, special=True)

    card_cls = mocker.patch("ui.duel_messages.summoning.Card", return_value=NamedCard("Parsed"))
    data = b"\x3c" + struct.pack("I", 1) + struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    assert summoning.msg_summoning(client, data, len(data)) == b""
    card_cls.assert_called_with(1)


def test_confirm_decktop_for_player_and_opponent(mocker):
    from ui.duel_messages import confirm_decktop

    client, _stack = _client(mocker)
    card_cls = mocker.patch("ui.duel_messages.confirm_decktop.Card")
    card_cls.side_effect = [NamedCard("Alpha"), NamedCard("Beta"), NamedCard("Gamma")]

    own_data = (
        b"\x19"
        + struct.pack("B", 0)
        + struct.pack("I", 3)
        + struct.pack("I", 10) + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("I", 0)
        + struct.pack("I", 0) + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("I", 1)
        + struct.pack("I", 20) + struct.pack("B", 0) + struct.pack("B", 0) + struct.pack("I", 2)
    )
    confirm_decktop.msg_confirm_decktop(client, own_data, len(own_data))

    other_data = (
        b"\x19"
        + struct.pack("B", 1)
        + struct.pack("I", 1)
        + struct.pack("I", 30) + struct.pack("B", 1) + struct.pack("B", 0) + struct.pack("I", 0)
    )
    confirm_decktop.msg_confirm_decktop(client, other_data, len(other_data))

    from core import utils
    assert "Top of your deck: Alpha, Beta" in utils.output.call_args_list[0].args[0]
    assert "opponent checked" in utils.output.call_args_list[1].args[0]


def test_toss_coin_and_dice_messages(mocker):
    from ui.duel_messages import toss

    client, _stack = _client(mocker)
    toss.variables.LANGUAGE_HANDLER.strings = {
        "system": {60: "Heads", 61: "Tails", 1623: "Coin toss:", 1624: "Dice roll:"}
    }

    assert toss.msg_toss_coin(client, b"\x82" + struct.pack("BBB", 0, 2, 1) + struct.pack("B", 0), 5) == b""
    toss.msg_toss_dice(client, b"\x83" + struct.pack("BBBB", 0, 2, 3, 6), 5)

    from core import utils
    assert utils.output.call_args_list[0].args[0] == "Coin toss: Heads, Tails"
    assert utils.output.call_args_list[1].args[0] == "Dice roll: 3, 6"


def test_counter_messages_add_remove_and_unknown_card(mocker):
    from ui.duel_messages import counters

    client, _stack = _client(mocker)
    counters.variables.LANGUAGE_HANDLER.strings = {"counter": {5: "Spell Counter"}}
    card = NamedCard("Counter Holder")
    client.get_card.return_value = card

    data = b"\x65" + struct.pack("h", 5) + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("B", 2) + struct.pack("h", 3)
    counters.msg_add_counter(client, data, len(data))
    counters.msg_remove_counter(client, data, len(data))
    counters.update_counters("add", 99, 1, None)

    from core import utils
    assert "3 Spell Counter added to Counter Holder" in utils.output.call_args_list[0].args[0]
    assert "3 Spell Counter removed from Counter Holder" in utils.output.call_args_list[1].args[0]
    assert "Counter 99" in utils.output.call_args_list[2].args[0]


def test_new_turn_updates_client_and_audio(mocker):
    from ui.duel_messages import new_turn

    client, stack = _client(mocker)
    client.turn_count = 0
    client.player = MagicMock()

    new_turn.msg_new_turn(client, b"\x28" + struct.pack("B", 0), 2)
    assert client.turn_count == 1
    assert client.is_it_my_turn is True
    client.player.clear_all.assert_called_once()
    stack.play_duel_sound_effect.assert_called_with("new_turn_me")

    new_turn.new_turn(client, 1)
    assert client.is_it_my_turn is False
    stack.play_duel_sound_effect.assert_called_with("new_turn_opponent")

    client.player = None
    new_turn.new_turn(client, 0)
    assert client.player is not None


def test_selected_and_targeting_messages(mocker):
    from ui.duel_messages import card_selected, card_targetting

    client, stack = _client(mocker)
    location = MagicMock()
    location.to_human_readable.return_value = "my monster zone"
    mocker.patch("ui.duel_messages.card_selected.LocationConversion", return_value=location)

    selected_data = b"\x50" + struct.pack("I", 1) + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("I", 2) + struct.pack("I", 3)
    card_selected.msg_card_selected(client, selected_data, len(selected_data))
    card_selected.card_selected(client, [location])

    attacker = NamedCard("Attacker")
    target = NamedCard("Target")
    client.get_card.side_effect = [attacker, target, attacker, target]
    target_data = (
        b"\x60"
        + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("I", 2) + struct.pack("I", 3)
        + struct.pack("B", 1) + struct.pack("B", 1) + struct.pack("I", 4) + struct.pack("I", 5)
    )

    card_targetting.msg_card_target(client, target_data, len(target_data))
    card_targetting.msg_cancel_card_target(client, target_data, len(target_data))

    client.get_card.side_effect = [None, target]
    direct = mocker.patch("ui.duel_messages.card_targetting.card_target")
    card_targetting.msg_card_target(client, target_data, len(target_data))
    direct.assert_called_with(client, None, target, False)

    from core import utils
    assert any("targets" in call.args[0] for call in utils.output.call_args_list)
    assert any("cancels targeting" in call.args[0] for call in utils.output.call_args_list)
    stack.play_duel_sound_effect.assert_any_call("aim")


def test_shuffle_deck_damage_equip_and_set_messages(mocker):
    from game.card import card_constants
    from game.player import Player
    from ui.duel_messages import damage_step_damage, equip, set, shuffle_deck

    client, stack = _client(mocker)
    client.player = SimpleNamespace(
        lifepoints=8000,
        opponent_lifepoints=8000,
        update_lifepoints=MagicMock(),
    )

    def update_lifepoints(value, opponent=False):
        if opponent:
            client.player.opponent_lifepoints = value
        else:
            client.player.lifepoints = value

    client.player.update_lifepoints.side_effect = update_lifepoints
    damage_step_damage.damage(client, 0, 700)
    damage_step_damage.damage(client, 1, 500)
    damage_step_damage.msg_damage(client, b"\x5b" + struct.pack("B", 0) + struct.pack("I", 300), 6)
    assert client.player.lifepoints == 7000
    assert client.player.opponent_lifepoints == 7500

    assert shuffle_deck.msg_shuffle_deck(client, b"\x20" + struct.pack("B", 0), 2) == b""
    shuffle_deck.shuffle_deck(client, 1)
    stack.play_duel_sound_effect.assert_any_call("shuffle")

    equip.equip(client, NamedCard("Equip"), NamedCard("Target"))
    client.get_card.side_effect = [NamedCard("Equip"), NamedCard("Target")]
    target_data = (
        b"\x5d"
        + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("I", 2) + struct.pack("I", 3)
        + struct.pack("B", 1) + struct.pack("B", 1) + struct.pack("I", 4) + struct.pack("I", 5)
    )
    equip.msg_equip(client, target_data, len(target_data))

    loc = MagicMock()
    loc.to_human_readable.return_value = "spell zone"
    mocker.patch("ui.duel_messages.set.LocationConversion.from_card_location", return_value=loc)
    set_card = NamedCard("Set Card")
    set.set(client, set_card)
    set_card.controller = 1
    set.set(client, set_card)
    card_cls = mocker.patch("ui.duel_messages.set.Card", return_value=NamedCard("Parsed Set"))
    data = (
        b"\x36"
        + struct.pack("I", 123)
        + struct.pack("B", 0)
        + struct.pack("B", card_constants.LOCATION.SPELL_AND_TRAP_ZONE)
        + struct.pack("I", 1)
        + struct.pack("I", card_constants.POSITION.FACE_DOWN)
    )
    set.msg_set(client, data, len(data))
    card_cls.assert_called_with(123)


def test_lpupdate_reverse_deck_and_battle_parser(mocker):
    from game.card import card_constants
    from ui.duel_messages import damage_step_battle, lpupdate, reverse_deck

    client, stack = _client(mocker)
    lpsource = MagicMock()
    client.player.update_lifepoints.return_value = lpsource
    stack.sound_effects_audio_manager.sources = {"lp": lpsource}
    mocker.patch("ui.duel_messages.lpupdate.wx.Yield", side_effect=lambda: stack.sound_effects_audio_manager.sources.clear())

    lpupdate.msg_lpupdate(client, b"\x5e" + struct.pack("B", 0) + struct.pack("I", 100), 6)
    client.player.update_lifepoints.assert_called_with(100)
    stack.play_duel_sound_effect.assert_called_with("lpend")

    client.player.update_lifepoints.return_value = MagicMock()
    lpupdate.lpupdate(client, 1, 0)
    client.player.update_lifepoints.assert_called_with(0, True)
    stack.play_duel_sound_effect.assert_called_with("lpzero")

    reverse_deck.msg_reversedeck(client, b"\x25", 1)

    attacker = NamedCard("Attacker", card_type=card_constants.TYPE.MONSTER)
    target = NamedCard("Target", card_type=card_constants.TYPE.LINK)
    client.get_card.side_effect = [attacker, target]
    data = b"\x6f"
    data += struct.pack("B", 0) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 0) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    data += struct.pack("I", 1800) + struct.pack("I", 1200) + struct.pack("B", 0)
    data += struct.pack("B", 1) + struct.pack("B", card_constants.LOCATION.MONSTER_ZONE) + struct.pack("I", 1) + struct.pack("I", card_constants.POSITION.FACE_UP_ATTACK)
    data += struct.pack("I", 1500) + struct.pack("I", 0) + struct.pack("B", 0)
    damage_step_battle.msg_battle(client, data, len(data))

    from core import utils
    assert any("all decks are now reversed" in call.args[0] for call in utils.output.call_args_list)


def test_life_point_cost_and_recovery_message_parsers(mocker):
    from ui.duel_messages import pay_cost, recover

    client, _stack = _client(mocker)
    client.player = SimpleNamespace(
        lifepoints=8000,
        opponent_lifepoints=8000,
        update_lifepoints=MagicMock(),
    )

    def update_lifepoints(value, opponent=False):
        if opponent:
            client.player.opponent_lifepoints = value
        else:
            client.player.lifepoints = value

    client.player.update_lifepoints.side_effect = update_lifepoints

    pay_cost.msg_pay_lpcost(client, b"\x64" + struct.pack("B", 0) + struct.pack("I", 1000), 6)
    pay_cost.msg_pay_lpcost(client, b"\x64" + struct.pack("B", 1) + struct.pack("I", 500), 6)
    recover.msg_recover(client, b"\x5c" + struct.pack("B", 0) + struct.pack("I", 300), 6)
    recover.msg_recover(client, b"\x5c" + struct.pack("B", 1) + struct.pack("I", 200), 6)

    assert client.player.lifepoints == 7300
    assert client.player.opponent_lifepoints == 7700


def test_short_duel_message_handlers_do_not_raise(mocker):
    from game.card import card_constants
    from ui.duel_messages import (
        attack_disabled,
        damage_step_end,
        damage_step_start,
        field_disabled,
        player_hint,
        shuffle_other,
        shuffle_set_card,
        waiting,
    )

    client, stack = _client(mocker)
    zone = MagicMock()
    zone.to_human_readable.return_value = "disabled monster zone"
    mocker.patch("ui.duel_messages.field_disabled.LocationConversion.from_zone_key", return_value=zone)
    client.flag_to_usable_cardspecs.return_value = ["m1"]

    field_disabled.field_disabled(client, 1)
    field_disabled.msg_field_disabled(client, b"\x38" + struct.pack("I", 1), 5)

    player_hint.msg_player_hint(client, b"\x52" + struct.pack("B", 0) + struct.pack("B", 1) + struct.pack("Q", 999), 11)

    assert shuffle_other.msg_shuffle_hand(client, b"\x21" + struct.pack("B", 0) + struct.pack("I", 2) + struct.pack("I", 10) + struct.pack("I", 20), 14) == b""
    assert shuffle_other.msg_shuffle_extra_deck(client, b"\x27" + struct.pack("B", 1) + struct.pack("I", 1) + struct.pack("I", 30), 10) == b""
    shuffle_other.shuffle_others(client, 0, card_constants.LOCATION.DECK, 1, [40])
    stack.play_duel_sound_effect.assert_any_call("shuffle")

    shuffle_set_card.msg_shuffle_set_card(client, b"\x22" + struct.pack("B", card_constants.LOCATION.SPELL_AND_TRAP_ZONE) + struct.pack("B", 2), 3)

    attack_disabled.msg_attack_disabled(client, b"\x70", 1)
    damage_step_start.msg_begin_damage(client, b"\x71", 1)
    assert damage_step_end.msg_end_damage(client, b"\x72abc", 4) == b"abc"
    damage_step_end.damage_step_end(client)
    assert waiting.msg_waiting(client, b"\x03payload", 8) is None
    assert waiting.waiting(client, None) is None

    from core import utils
    assert any("Field locations" in call.args[0] for call in utils.output.call_args_list)
    assert any("Set cards on the field were shuffled." in call.args[0] for call in utils.output.call_args_list)
    stack.play_duel_sound_effect.assert_any_call("phase/damage")
    stack.play_duel_sound_effect.assert_any_call("phase/damageend")
