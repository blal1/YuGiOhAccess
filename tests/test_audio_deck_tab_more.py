from unittest.mock import MagicMock

import pytest

from tests.test_ui_flows_more import FakeMenu, FakeStatus


def test_audio_manager_volume_play_stop_and_fade(mocker, tmp_path):
    from ui.audio import AudioManager

    mocker.patch.object(AudioManager, "__del__", lambda self: None)
    mocker.patch("ui.audio.variables.config", MagicMock())
    manager = AudioManager.__new__(AudioManager)
    manager.volume_config_key = "music_volume"
    manager.context = MagicMock()
    manager.listener = MagicMock()
    manager.source_volume = 0.5
    manager.buffer_cache = {}
    manager.sources = {}
    manager.is_fading = False

    source = MagicMock()
    manager.sources = {"old": source}
    manager.decrease_volume(1)
    assert manager.source_volume == 0.0
    assert source.gain == 0.0
    manager.increase_volume(2)
    assert manager.source_volume == 1.0
    manager.set_volume(-1)
    assert manager.source_volume == 0.0
    manager.set_volume(0.4)
    assert manager.get_volume() == 0.4

    sound_dir = tmp_path / "sounds"
    sound_dir.mkdir()
    (sound_dir / "click.wav").write_bytes(b"x")
    mocker.patch("ui.audio.variables.LOCAL_DATA_DIR", tmp_path)
    fake_file = MagicMock()
    fake_file.channels = 1
    fake_file.samplerate = 44100
    fake_file.read.return_value.tobytes.return_value = b"pcm"
    mocker.patch("ui.audio.soundfile.SoundFile", return_value=fake_file)
    buffer = MagicMock()
    source = MagicMock()
    manager.context.gen_buffer.return_value = buffer
    manager.context.gen_source.return_value = source
    played = manager.play_audio("click.wav", looping=True, x=1.0)
    assert played is source
    assert source.spatialize is True
    assert source.looping is True
    buffer.set_data.assert_called_once()

    from ui.audio import cyal
    source.state = cyal.SourceState.PLAYING
    assert manager.is_playing(source) is True

    manager.sources = {sound_dir / "click.wav": source}
    manager._stop_audio_after_duration(source, 0)
    assert manager.sources == {}

    source1 = MagicMock(gain=0.005)
    source2 = MagicMock(gain=0.005)
    manager.sources = {"a": source1, "b": source2}
    manager._fade_out_all_audio(["a", "b"])
    assert manager.sources == {}
    assert manager.is_fading is False

    manager.sources = {"a": MagicMock()}
    manager.stop_all_audio()
    assert manager.sources == {}
    del manager


def test_audio_manager_init_del_cached_stereo_and_recursive_fade(mocker, tmp_path):
    from ui import audio
    from ui.audio import AudioManager

    fake_context = MagicMock()
    fake_context.listener = MagicMock()
    mocker.patch("ui.audio._CONTEXT", fake_context)
    config = MagicMock()
    config.get.return_value = 0.25
    mocker.patch("ui.audio.variables.config", config)

    manager = AudioManager("sound_volume")
    assert manager.context is fake_context
    assert manager.listener.gain == 0.7
    assert manager.source_volume == 0.25

    sound_dir = tmp_path / "sounds"
    sound_dir.mkdir()
    (sound_dir / "stereo.ogg").write_bytes(b"x")
    mocker.patch("ui.audio.variables.LOCAL_DATA_DIR", tmp_path)
    fake_file = MagicMock()
    fake_file.channels = 2
    fake_file.samplerate = 48000
    fake_file.read.return_value.tobytes.return_value = b"pcm"
    mocker.patch("ui.audio.soundfile.SoundFile", return_value=fake_file)
    buffer = MagicMock()
    first_source = MagicMock()
    fake_context.gen_buffer.return_value = buffer
    fake_context.gen_source.return_value = first_source

    played = manager.play_audio("stereo.ogg")

    assert played is first_source
    assert first_source.spatialize is False
    buffer.set_data.assert_called_once()
    assert buffer.set_data.call_args.kwargs["format"] == audio.cyal.BufferFormat.STEREO16

    first_source.play.reset_mock()
    again = manager.play_audio("stereo.ogg", x=0.0, y=0.0, z=0.0)
    assert again is first_source
    assert fake_context.gen_source.call_count == 1
    first_source.play.assert_called_once()

    delayed = MagicMock()
    mocker.patch("ui.audio.threading.Thread", return_value=delayed)
    assert manager.play_audio_for_specified_duration("stereo.ogg", 5) is first_source
    delayed.start.assert_called_once()

    fading_source = MagicMock(gain=0.02)
    manager.sources = {"fade": fading_source}
    sleep = mocker.patch("ui.audio.time.sleep")
    manager._fade_out_all_audio(["fade"])
    assert sleep.called
    assert manager.sources == {}
    assert manager.is_fading is False

    manager.sources = {"stereo": first_source}
    manager.__del__()
    config.set.assert_called_with("sound_volume", 0.25)
    mocker.patch.object(AudioManager, "__del__", lambda self: None)
    del manager


def _patch_deck_editor(mocker, tmp_path):
    from ui import deck_editor_ui

    mocker.patch("ui.deck_editor_ui.VerticalMenu", FakeMenu)
    mocker.patch("ui.deck_editor_ui.utils.get_ui_stack", return_value=MagicMock())
    mocker.patch("ui.deck_editor_ui.utils.output")
    mocker.patch("ui.deck_editor_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    deck_editor_ui.variables.DECK_DIR = tmp_path
    deck_editor_ui.variables.LANGUAGE_HANDLER = MagicMock()
    return deck_editor_ui


def test_deck_editor_menus_search_and_load(mocker, tmp_path):
    deck_editor_ui = _patch_deck_editor(mocker, tmp_path)
    return_to = MagicMock()
    real_edit_deck = deck_editor_ui.edit_deck

    menu = deck_editor_ui.deck_editor_main_menu.__wrapped__(return_to)
    assert any(item[0] == "New Deck" for item in menu.items)

    input_cls = mocker.patch("ui.deck_editor_ui.InputUI")
    input_cls.return_value.show.return_value = ""
    mocker.patch("ui.deck_editor_ui.deck_editor_main_menu")
    deck_editor_ui.new_deck.__wrapped__(return_to)
    input_cls.return_value.show.return_value = "MyDeck"
    mocker.patch("ui.deck_editor_ui.edit_deck")
    deck_editor_ui.new_deck.__wrapped__(return_to)
    deck_editor_ui.edit_deck.assert_called()

    menu = deck_editor_ui.pick_deck_to_edit.__wrapped__(return_to)
    assert menu is None
    (tmp_path / "a.json").write_text("{}")
    menu = deck_editor_ui.pick_deck_to_edit.__wrapped__(return_to)
    assert any(item[0] == "a" for item in menu.items)

    parsed = MagicMock(cards=[1, 2], side=[3])
    mocker.patch("ui.deck_editor_ui.Deck.from_json", return_value=parsed)
    deck_editor_ui.load_and_edit(tmp_path / "a.json", return_to)
    deck_editor_ui.edit_deck.assert_called_with("a", {"main": [1, 2], "side": [3]}, return_to)

    (tmp_path / "b.ydke").write_text("ydke://x")
    mocker.patch("ui.deck_editor_ui.Deck.from_ydke", return_value=parsed)
    deck_editor_ui.load_and_edit(tmp_path / "b.ydke", return_to)

    deck_data = {"main": [1, 2, 3], "side": [4]}
    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", side_effect=lambda code: code == 3)
    menu = real_edit_deck.__wrapped__("Deck", deck_data, return_to)
    assert any("Main deck" in item[0] for item in menu.items)

    db = MagicMock()
    db.execute.return_value.fetchall.return_value = [(10, "Alpha")]
    deck_editor_ui.variables.LANGUAGE_HANDLER.primary_database = db
    input_cls.return_value.show.return_value = "alpha"
    menu = deck_editor_ui.search_card_to_add.__wrapped__("Deck", deck_data, return_to)
    assert any(item[0] == "Alpha" for item in menu.items)
    db.execute.return_value.fetchall.return_value = []
    assert deck_editor_ui.search_card_to_add.__wrapped__("Deck", deck_data, return_to) is None


def test_deck_editor_add_remove_view_save_paths(mocker, tmp_path):
    deck_editor_ui = _patch_deck_editor(mocker, tmp_path)
    return_to = MagicMock()
    card_cls = mocker.patch("ui.deck_editor_ui.Card")
    card_cls.return_value.get_name.return_value = "Card"
    card_cls.return_value.__str__.return_value = "Card detail"
    deck_data = {"main": [], "side": []}
    mocker.patch("ui.deck_editor_ui.edit_deck")

    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=False)
    deck_editor_ui.add_card_to_deck("Deck", deck_data, 1, return_to)
    assert deck_data["main"] == [1]

    deck_data["main"] = [1, 1, 1]
    deck_editor_ui.add_card_to_deck("Deck", deck_data, 1, return_to)
    assert deck_data["main"] == [1, 1, 1]

    deck_data["main"] = list(range(deck_editor_ui.MAX_MAIN_DECK))
    deck_editor_ui.add_card_to_deck("Deck", deck_data, 999, return_to)

    mocker.patch("ui.deck_editor_ui._is_extra_deck_card", return_value=True)
    deck_data["main"] = list(range(deck_editor_ui.MAX_EXTRA_DECK))
    deck_editor_ui.add_card_to_deck("Deck", deck_data, 999, return_to)

    deck_data = {"main": [1], "side": []}
    menu = deck_editor_ui.choose_add_destination.__wrapped__("Deck", deck_data, 2, return_to)
    assert any(item[0] == "Add to side deck" for item in menu.items)
    deck_editor_ui.add_card_to_side("Deck", deck_data, 2, return_to)
    assert 2 in deck_data["side"]
    deck_data["side"] = list(range(deck_editor_ui.MAX_SIDE_DECK))
    deck_editor_ui.add_card_to_side("Deck", deck_data, 99, return_to)

    deck_data = {"main": [1, 1, 2], "side": []}
    menu = deck_editor_ui.remove_card_menu.__wrapped__("Deck", deck_data, "main", return_to)
    assert any("x2" in item[0] for item in menu.items)
    deck_editor_ui._do_remove("Deck", deck_data, "main", 1, return_to)
    assert deck_data["main"].count(1) == 1
    assert deck_editor_ui.remove_card_menu.__wrapped__("Deck", {"main": [], "side": []}, "main", return_to) is None

    menu = deck_editor_ui.view_deck_list.__wrapped__("Deck", {"main": [1, 1], "side": []}, "main", return_to)
    assert any("x2" in item[0] for item in menu.items)
    assert deck_editor_ui.view_deck_list.__wrapped__("Deck", {"main": [], "side": []}, "main", return_to) is None
    deck_editor_ui._read_card_detail(1)
    deck_editor_ui.utils.output.assert_called()

    deck_data = {"main": [3, 1, 2, 1], "side": []}
    groups = deck_editor_ui._group_cards_combined(deck_data["main"])
    assert groups[1] == 2

    deck = MagicMock()
    deck.to_json.return_value = "{}"
    mocker.patch("ui.deck_editor_ui.Deck", return_value=deck)
    mocker.patch("ui.deck_editor_ui._validate_deck_for_save", return_value=None)
    deck_editor_ui.save_deck("Bad:Name", {"main": [1], "side": []}, return_to)
    assert (tmp_path / "Bad_Name.json").exists()

    deck.to_ydke.return_value = "ydke://x"
    mocker.patch("ui.deck_editor_ui.wx.TextDataObject", side_effect=lambda text: text)
    deck_editor_ui.wx.TheClipboard = MagicMock()
    deck_editor_ui.export_deck_string("Deck", {"main": [1], "side": []}, return_to)
    deck_editor_ui.wx.TheClipboard.SetData.assert_called_with("ydke://x")


def test_tab_order_next_previous_and_validation():
    from ui.tab_order import DuelFieldTabOrder

    order = DuelFieldTabOrder()
    assert order.resolve_next_tab_order() is None
    assert order.resolve_previous_tab_order() is None
    with pytest.raises(ValueError):
        order.set_tabable_items("bad")
    order.set_tabable_items(["a", "b"])
    assert order.resolve_next_tab_order() == "a"
    assert order.resolve_next_tab_order() == "b"
    assert order.resolve_next_tab_order() == "a"
    assert order.resolve_previous_tab_order() == "b"
    assert order.resolve_previous_tab_order() == "a"
