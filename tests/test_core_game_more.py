import io
import sqlite3
import struct
import time
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


def test_player_clear_all_and_property_validation(mocker):
    from game.player import Player

    player = Player.__new__(Player)
    player._chaining_cards = [1]
    player._summonable = [1]
    player._special_summonable = [1]
    player._repositionable = [1]
    player._monster_settable = [1]
    player._spell_settable = [1]
    player._activatable = [1]
    player._attackable = [1]
    player._can_go_to_battle_phase = 1
    player._can_go_to_main_phase2 = 1
    player._can_go_to_end_phase = 1
    player._can_shuffle = 1

    player.clear_all()

    assert player.chaining_cards == []
    assert player.summonable == []
    assert player.special_summonable == []
    assert player.repositionable == []
    assert player.monster_settable == []
    assert player.spell_settable == []
    assert player.activatable == []
    assert player.attackable == []
    assert player.can_go_to_battle_phase is False
    assert player.can_go_to_main_phase2 is False
    assert player.can_go_to_end_phase is False
    assert player.can_shuffle == 0

    for attr in [
        "chaining_cards",
        "summonable",
        "special_summonable",
        "repositionable",
        "monster_settable",
        "spell_settable",
        "activatable",
        "attackable",
    ]:
        with pytest.raises(ValueError):
            setattr(player, attr, "not a list")

    for attr in ["can_go_to_battle_phase", "can_go_to_main_phase2", "can_go_to_end_phase"]:
        with pytest.raises(ValueError):
            setattr(player, attr, True)
        with pytest.raises(ValueError):
            setattr(player, attr, "1")


def test_player_lifepoints_and_timer_sfx(mocker, tmp_path):
    from game.player import CountdownTimer, Player

    ui_stack = MagicMock()
    mocker.patch("core.utils.get_ui_stack", return_value=ui_stack)

    player = Player.__new__(Player)
    player.lifepoints = 4000
    player.opponent_lifepoints = 4000
    player.duel_music = MagicMock()
    player.duel_music_filepath = tmp_path / "duel_standard" / "1.flac"
    mocker.patch.object(player, "handle_potential_music_change")

    source = player.update_lifepoints(3500)
    assert player.lifepoints == 3500
    assert source == ui_stack.sound_effects_audio_manager.play_audio_for_specified_duration.return_value

    player.update_lifepoints(4500, opponent=True)
    assert player.opponent_lifepoints == 4500
    ui_stack.play_duel_sound_effect.assert_any_call("lpearn")

    timer = CountdownTimer.__new__(CountdownTimer)
    for seconds, expected in [(0, "timer/zero"), (30, "timer/30"), (10, "timer/even"), (9, "timer/odd")]:
        ui_stack.reset_mock()
        timer.seconds = seconds
        timer.handle_potential_sfx()
        assert any(expected in str(call) for call in ui_stack.play_duel_sound_effect.call_args_list)


def test_player_init_music_transitions_and_timer_methods(mocker, tmp_path):
    from game.player import CountdownTimer, Player

    for folder in ("duel_standard", "duel_losing", "duel_winning"):
        music_dir = tmp_path / "sounds" / "music" / folder
        music_dir.mkdir(parents=True)
        (music_dir / f"{folder}.ogg").write_bytes(b"")

    stack = MagicMock()
    stack.music_audio_manager.play_audio.return_value = MagicMock()
    mocker.patch("game.player.utils.get_ui_stack", return_value=stack)
    mocker.patch("game.player.variables.LOCAL_DATA_DIR", tmp_path)
    mocker.patch("game.player.random.choice", side_effect=lambda items: list(items)[0])
    timer_cls = mocker.patch("game.player.CountdownTimer", return_value="timer")

    player = Player(8000, 8000)

    assert player.turn_timer == "timer"
    timer_cls.assert_called()
    stack.music_audio_manager.play_audio.assert_called_with("music/duel_standard/duel_standard.ogg", looping=True)

    player.duel_music = MagicMock()
    player.lifepoints = 1000
    player.opponent_lifepoints = 8000
    player.duel_music_filepath = tmp_path / "sounds" / "music" / "duel_standard" / "duel_standard.ogg"
    player.handle_potential_music_change()
    stack.music_audio_manager.play_audio.assert_called_with("music/duel_losing/duel_losing.ogg", looping=True)

    player.duel_music = MagicMock()
    player.lifepoints = 9000
    player.opponent_lifepoints = 1000
    player.duel_music_filepath = tmp_path / "sounds" / "music" / "duel_losing" / "duel_losing.ogg"
    player.handle_potential_music_change()
    stack.music_audio_manager.play_audio.assert_called_with("music/duel_winning/duel_winning.ogg", looping=True)

    player.duel_music = MagicMock()
    player.lifepoints = 4000
    player.opponent_lifepoints = 4000
    player.duel_music_filepath = tmp_path / "sounds" / "music" / "duel_winning" / "duel_winning.ogg"
    player.handle_potential_music_change()
    stack.music_audio_manager.play_audio.assert_called_with("music/duel_standard/duel_standard.ogg", looping=True)

    existing_timer = MagicMock()
    player._turn_timer = existing_timer
    player.turn_timer = 55
    existing_timer.update.assert_called_with(55)
    player.attackable = [1]
    assert player.attackable == [1]

    class FakeLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    timer = CountdownTimer.__new__(CountdownTimer)
    timer.lock = FakeLock()
    timer.running = False
    timer.thread = MagicMock()
    timer.seconds = 3
    thread_cls = mocker.patch("game.player.threading.Thread")
    timer.update(10)
    assert timer.get_remaining_time() == 10
    thread_cls.return_value.start.assert_called_once()
    timer.stop()
    timer.thread.join.assert_called_once()


def _fake_language_handler_for_card(mocker, row=None, text_row=None):
    lang = MagicMock()
    db = MagicMock()
    def execute(sql, args=()):
        cursor = MagicMock()
        if "from datas" in sql.lower():
            cursor.fetchone.return_value = row
        elif "select name" in sql.lower():
            cursor.fetchone.return_value = [text_row[1]] if text_row else None
        elif "select desc" in sql.lower():
            cursor.fetchone.return_value = [text_row[2]] if text_row else None
        elif "from texts" in sql.lower():
            cursor.fetchone.return_value = text_row
        else:
            cursor.fetchone.return_value = None
        return cursor
    db.execute.side_effect = execute
    lang.primary_database = db
    lang.cdb = db
    system_strings = {1050 + i: f"Type {i}" for i in range(40)}
    system_strings.update({1020: "Warrior", 1010: "Earth", 999: "System fallback"})
    lang.strings = {"system": system_strings, "setname": {0x1: "Test Archetype"}}
    lang._ = lambda s: s
    mocker.patch("game.card.card.variables.LANGUAGE_HANDLER", lang)
    return lang


def test_card_unknown_and_known_card_behaviour(mocker):
    from core.exceptions import CardNotFoundException
    from game.card import card_constants
    from game.card.card import Card

    _fake_language_handler_for_card(mocker, row=None)
    hidden = Card(0)
    assert hidden.code == 0
    hidden.set_location_and_position_info(0, card_constants.LOCATION.HAND, 0, card_constants.POSITION.FACE_DOWN)
    assert hidden.get_position() == "face down"

    with pytest.raises(CardNotFoundException):
        _fake_language_handler_for_card(mocker, row=None)
        Card(123)

    row = {
        "alias": 0,
        "setcode": 0x1,
        "type": int(card_constants.TYPE.MONSTER | card_constants.TYPE.EFFECT),
        "level": 4,
        "atk": 1900,
        "def": 1200,
        "race": 1,
        "attribute": 1,
        "category": 0,
    }
    text_row = [123, "Test Warrior", "A test card.", "Effect text", ""]
    lang = _fake_language_handler_for_card(mocker, row=row, text_row=text_row)
    lang.get_card_translation.return_value = None

    card = Card(123)
    card.set_location_and_position_info(0, card_constants.LOCATION.MONSTER_ZONE, 2, card_constants.POSITION.FACE_UP_ATTACK)

    assert card.get_name() == "Test Warrior"
    assert card.get_description() == "A test card."
    assert "Attack: 1900 Defense: 1200 Level: 4" in str(card)
    assert "Archetype: Test Archetype" in str(card)
    assert card.get_effect_description(0) == "Activate this card."
    assert card.get_effect_description(123 * 16) == "Effect text"
    assert card.get_effect_description(999) == "System fallback"
    assert card.get_position() == "face-up attack"
    assert repr(card) == "Test Warrior"

    same = Card.__new__(Card)
    same.code = 123
    same.controller = 0
    same.location = card.location
    same.sequence = 2
    same.position = card.position
    assert card == same
    assert same in card
    assert card != object()
    assert lang.primary_database.execute.call_count >= 2

    lang.get_card_translation.return_value = {"name": "Guerrier de test", "desc": "Une carte de test."}
    assert card.get_name() == "Guerrier de test"
    assert card.get_description() == "Une carte de test."


def test_card_positions_extra_and_link_markers(mocker):
    from game.card import card_constants
    from game.card.card import Card

    card = Card.__new__(Card)
    card.code = 1
    card.name = "Link"
    card.desc = "desc"
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.LINK
    card.attribute = 0
    card.race = 0
    card.attack = 1000
    card.defense = 0o0001 | 0o0200
    card.level = 2
    card.location = card_constants.LOCATION.EXTRA
    card.position = card_constants.POSITION.FACE_UP_DEFENSE
    card.strings = []
    lang = MagicMock()
    lang._ = lambda s: s
    lang.strings = {"system": {1050 + i: f"Type {i}" for i in range(40)}}
    lang.primary_database.execute.return_value.fetchone.return_value = None
    lang.cdb.execute.return_value.fetchone.return_value = None
    mocker.patch("game.card.card.variables.LANGUAGE_HANDLER", lang)

    assert card.extra is True
    assert card.get_position() == "face-up"
    assert "bottom left" in card.get_link_markers()
    assert "top" in card.get_link_markers()
    assert "Link Markers" in str(card)

    card.position = card_constants.POSITION.FACE_DOWN_DEFENSE
    assert card.get_position() == "face down"
    card.location = card_constants.LOCATION.MONSTER_ZONE
    assert card.get_position() == "face-down defense"


def test_card_remaining_positions_effects_and_xyz_branches(mocker):
    from game.card import card_constants
    from game.card.card import Card

    lang = MagicMock()
    lang._ = lambda s: s
    system_strings = {1050 + i: f"Type {i}" for i in range(80)}
    system_strings[777] = "System option"
    lang.strings = {
        "system": system_strings,
        "setname": {},
    }
    lang.primary_database.execute.return_value.fetchone.return_value = None
    lang.cdb.execute.return_value.fetchone.return_value = None
    mocker.patch("game.card.card.variables.LANGUAGE_HANDLER", lang)

    card = Card.__new__(Card)
    card.code = 42
    card.name = "XYZ"
    card.desc = "desc"
    card.strings = ["", "local effect"]
    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.XYZ
    card.attribute = 0
    card.race = 0
    card.setcode = 0
    card.attack = 1000
    card.defense = 2000
    card.level = 4
    card.location = card_constants.LOCATION.MONSTER_ZONE
    card.position = card_constants.POSITION.FACE_UP_DEFENSE
    card.xyz_materials = []
    assert "Rank: 4" in str(card)
    assert "no xyz materials attached" in str(card)

    material = Card.__new__(Card)
    material.code = 7
    material.name = "Material"
    material.get_name = lambda: "Material"
    card.xyz_materials = [material]
    assert "attached xyz materials" in str(card)

    del card.xyz_materials
    assert "XYZ" in str(card)

    card.type = card_constants.TYPE.MONSTER | card_constants.TYPE.PENDULUM
    card.lscale = 1
    card.rscale = 8
    assert "Pendulum scale: 1/8" in str(card)

    packed = 0 | (int(card_constants.LOCATION.GRAVE) << 8) | (3 << 16) | (int(card_constants.POSITION.FACE_DOWN_ATTACK) << 24)
    card.set_location_and_position_by_unpacking(packed)
    assert card.sequence == 3
    assert card.get_position() == "face-down attack"
    card.position = card_constants.POSITION.FACE_UP_DEFENSE
    card.location = card_constants.LOCATION.MONSTER_ZONE
    assert card.get_position() == "face-up defense"
    card.position = card_constants.POSITION.FACE_UP
    assert card.get_position() == "face-up"

    assert card.get_strings(999) == card.strings
    assert card.get_effect_description((10001 << 4) + 1) == "local effect"
    assert card.get_effect_description(123456, existing=True) == ""


def test_language_handler_parse_add_primary_and_search(mocker, tmp_path):
    from game.language_handler import LanguageHandler

    data_dir = tmp_path / "data"
    locales = data_dir / "locales" / "en"
    locales.mkdir(parents=True)
    (locales / "strings.conf").write_text("!system 1 One\n!system 0x2 Two\n!setcode 3 Ignored\n", encoding="utf-8")

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", data_dir)
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", tmp_path / "app")
    mocker.patch("game.language_handler.variables.config", {"language": "english"})

    handler = LanguageHandler()
    handler.add("English", "EN")
    assert handler.is_loaded("english")
    handler.set_primary_language("english")
    assert handler.get_strings("english")["system"][1] == "One"
    assert handler.get_strings("english")["system"][2] == "Two"

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("create table texts(id integer, name text)")
    db.executemany("insert into texts values (?, ?)", [(1, "Alpha"), (2, "Beta")])
    handler.languages["english"]["db"] = db
    assert handler.get_cards_by_partial_name("a") == {"Alpha": 1, "Beta": 2}
    assert handler.get_cards_by_partial_name("zzz") == {}

    handler.languages["french"] = {"short": "fr", "card_translations": {1: {"name": "Dragon Blanc", "desc": "Desc"}}}
    handler.primary_language = "french"
    assert handler.get_card_translation(1)["name"] == "Dragon Blanc"
    assert handler.get_cards_by_partial_name("blanc") == {"Dragon Blanc": 1}

    with pytest.raises(Exception):
        handler.set_primary_language("missing")
    with pytest.raises(Exception):
        handler.get_language("missing")


def test_language_handler_add_available_languages_and_fallback(mocker, tmp_path):
    from game.language_handler import LanguageHandler

    data_dir = tmp_path / "data"
    en_dir = data_dir / "locales" / "en"
    fr_dir = data_dir / "locales" / "fr"
    en_dir.mkdir(parents=True)
    fr_dir.mkdir(parents=True)
    (en_dir / "strings.conf").write_text("!system 1 English\n!system 2 Fallback\n!setname 0x1 Archetype\n", encoding="utf-8")
    (fr_dir / "strings.conf").write_text("!system 1 Francais\n", encoding="utf-8")

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", data_dir)
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", tmp_path / "app")

    handler = LanguageHandler()
    handler.add_available_languages()

    assert handler.is_loaded("english")
    assert handler.is_loaded("french")
    assert not handler.is_loaded("german")
    assert handler.get_strings("french")["system"][1] == "Francais"
    assert handler.get_strings("french")["system"][2] == "Fallback"
    assert handler.get_strings("french")["setname"][1] == "Archetype"


def test_language_handler_connects_and_merges_card_databases(mocker, tmp_path):
    from core.exceptions import LanguageException
    from game.language_handler import LanguageHandler

    data_dir = tmp_path / "data"
    locale_dir = data_dir / "locales" / "en"
    db_dir = tmp_path / "app" / "sync" / "databases2" / "content"
    locale_dir.mkdir(parents=True)
    db_dir.mkdir(parents=True)
    (locale_dir / "strings.conf").write_text("!system 1 One\n", encoding="utf-8")

    def create_card_db(path, rows):
        db = sqlite3.connect(path)
        db.execute("create table datas(id integer, alias integer, setcode integer, type integer, level integer, atk integer, def integer, race integer, attribute integer, category integer)")
        db.execute("create table texts(id integer, name text, desc text)")
        db.executemany("insert into datas values (?, 0, 0, 1, 4, 1000, 1000, 1, 1, 0)", [(row[0],) for row in rows])
        db.executemany("insert into texts values (?, ?, ?)", rows)
        db.commit()
        db.close()

    create_card_db(db_dir / "cards.cdb", [(1, "Alpha", "A")])
    create_card_db(db_dir / "extra.cdb", [(2, "Beta", "B")])
    create_card_db(db_dir / "empty.cdb", [])

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", data_dir)
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", tmp_path / "app")
    mocker.patch("game.language_handler.variables.config", {"language": "english"})

    handler = LanguageHandler()
    handler.add("english", "en")
    handler.set_primary_language("english")
    handler.connect_all_databases()

    assert handler.primary_database.execute("select name from texts where id=1").fetchone()[0] == "Alpha"
    assert handler.cdb.execute("select name from texts where id=2").fetchone()[0] == "Beta"
    assert handler.strings["system"][1] == "One"

    handler.card_database_dir = tmp_path / "missing"
    with pytest.raises(LanguageException):
        handler._LanguageHandler__connect_database()


def test_language_handler_prefers_downloaded_multilingual_files(mocker, tmp_path):
    from game.language_handler import LanguageHandler

    data_dir = tmp_path / "data"
    en_dir = data_dir / "locales" / "en"
    app_dir = tmp_path / "app"
    base_db_dir = app_dir / "sync" / "databases2" / "content"
    fr_db_dir = app_dir / "sync" / "languages" / "content" / "Français"
    en_dir.mkdir(parents=True)
    base_db_dir.mkdir(parents=True)
    fr_db_dir.mkdir(parents=True)
    (en_dir / "strings.conf").write_text("!system 1 English\n!system 2 Fallback\n", encoding="utf-8")
    (fr_db_dir / "strings.conf").write_text("!system 1 Francais\n", encoding="utf-8")

    def create_card_db(path, rows):
        db = sqlite3.connect(path)
        db.execute("create table datas(id integer, alias integer, setcode integer, type integer, level integer, atk integer, def integer, race integer, attribute integer, category integer)")
        db.execute("create table texts(id integer, name text, desc text)")
        db.executemany("insert into datas values (?, 0, 0, 1, 4, 1000, 1000, 1, 1, 0)", [(row[0],) for row in rows])
        db.executemany("insert into texts values (?, ?, ?)", rows)
        db.commit()
        db.close()

    create_card_db(base_db_dir / "cards.cdb", [(1, "Blue-Eyes", "English")])
    create_card_db(fr_db_dir / "cards.cdb", [(1, "Dragon Blanc", "Francais")])

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", data_dir)
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", app_dir)
    mocker.patch("game.language_handler.variables.config", {"language": "french"})

    handler = LanguageHandler()
    handler.add_available_languages()
    handler.set_primary_language("french")
    handler.connect_all_databases()

    assert handler.is_loaded("french")
    assert handler.get_strings("french")["system"][1] == "Francais"
    assert handler.get_strings("french")["system"][2] == "Fallback"
    assert handler.primary_database.execute("select name from texts where id=1").fetchone()[0] == "Dragon Blanc"
    assert handler.get_card_translations() == {}


def test_language_handler_error_cache_and_download_paths(mocker, tmp_path):
    from game.language_handler import LanguageHandler

    data_dir = tmp_path / "data"
    en_dir = data_dir / "locales" / "en"
    en_dir.mkdir(parents=True)
    (en_dir / "strings.conf").write_text(
        "!system 1 English\n!victory bad Skipped\n!system 0x2 Hex\n",
        encoding="utf-8",
    )

    mocker.patch("game.language_handler.variables.LOCAL_DATA_DIR", data_dir)
    mocker.patch("game.language_handler.variables.APP_DATA_DIR", tmp_path / "app")
    handler = LanguageHandler()
    handler.languages = {}
    handler.primary_language = ""

    handler.add("missing", "zz")
    assert not handler.is_loaded("missing")

    handler.add("english", "en")
    assert handler.get_strings("english")["system"][2] == "Hex"
    assert "victory" not in handler.get_strings("english")

    handler.ensure_card_translations("spanish")
    assert "spanish" not in handler.languages

    cache_dir = handler.card_translation_dir
    cache_dir.mkdir(parents=True)
    (cache_dir / "french.json").write_text('{"cards": {"123": {"name": "Nom", "desc": "Texte"}}}', encoding="utf-8")
    handler.ensure_card_translations("french")
    handler.primary_language = "french"
    assert handler.get_card_translation(123)["name"] == "Nom"
    handler.ensure_card_translations("french")
    assert handler.get_card_translation(123)["name"] == "Nom"

    handler.languages.pop("french")
    (cache_dir / "french.json").write_text("{bad json", encoding="utf-8")
    response = MagicMock()
    response.json.return_value = {"data": [{"id": 7, "name": "Downloaded", "desc": "Desc"}, {"name": "No id"}]}
    get = mocker.patch("game.language_handler.requests.get", return_value=response)
    mocker.patch("game.language_handler.time.time", return_value=123456)

    handler.ensure_card_translations("french")

    get.assert_called_once()
    response.raise_for_status.assert_called_once()
    assert handler.get_card_translation(7)["name"] == "Downloaded"
    assert '"7"' in (cache_dir / "french.json").read_text(encoding="utf-8")

    handler.languages.pop("french")
    (cache_dir / "french.json").unlink()
    mocker.patch("game.language_handler.requests.get", side_effect=OSError("network"))
    handler.ensure_card_translations("french")
    handler.primary_language = "french"
    assert handler.get_card_translations() == {}


def test_utils_small_helpers_and_repo_update_paths(mocker, tmp_path):
    from core import utils

    assert utils.guess_items_in(["Alice", "Alfred", "Bob"], "al", "bob") == ["Alfred", "Alice"]
    assert utils.guess_items_in(["Alice"], "Alice", "Me") == ["Alice"]
    assert utils.extract_trailing_numbers("deck42") == 42
    assert utils.extract_trailing_numbers("deck") is None
    assert utils.sanitize_filename(" bad:name?.ydk ") == "bad_name_.ydk"
    assert utils.version_string_to_pretty("1.0.0a1") == "1.0.0 alpha 1"

    assert utils._repo_not_valid(tmp_path / "missing") is True
    file_path = tmp_path / "file"
    file_path.write_text("x")
    assert utils._repo_not_valid(file_path) is True
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert utils._repo_not_valid(empty_dir) is True

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "last_downloaded.txt").write_text("old")
    response = MagicMock()
    response.json.return_value = {"updated_at": "new"}
    response.raise_for_status.return_value = None
    mocker.patch("core.utils.requests.get", return_value=response)
    assert utils._should_redownload_repo("org/repo", repo) == (True, "new")

    mocker.patch("core.utils._should_redownload_repo", return_value=(False, "same"))
    assert utils.update_data_repo("repo", "org/repo", repo) is True
    mocker.patch("core.utils._should_redownload_repo", side_effect=RuntimeError("boom"))
    assert utils.update_data_repo("repo", "org/repo", repo) is False


def test_utils_download_repo_extracts_zip(mocker, tmp_path):
    from core import utils

    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("repo-master/file.txt", "content")

    response = MagicMock()
    response.__enter__.return_value = response
    response.iter_content.return_value = [zip_bytes.getvalue()]
    response.raise_for_status.return_value = None
    mocker.patch("core.utils.requests.get", return_value=response)

    target = tmp_path / "repo"
    utils._download_repo("org/repo", target, "updated")

    assert (target / "content" / "file.txt").read_text() == "content"
    assert (target / "last_downloaded.txt").read_text() == "updated"
