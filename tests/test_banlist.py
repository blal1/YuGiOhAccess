import pytest
from game.card.ydke import Deck
from game.edo import banlists

SINGLE_BANLIST_PATH = "tests/data/banlists/0TCG.lflist.conf"
BANLIST_FOLDER = "tests/data/banlists"
TCG_BANLIST_HASH = 3297508800

# make a function to reset the banlist manager
@pytest.fixture(autouse=True)
def reset_banlist_manager():
    manager = banlists.BanlistManager()
    manager.banlists = []
    manager.banlists_path = None
    manager._initialized = False

def test_load_banlist(reset_banlist_manager):
    manager = banlists.BanlistManager(load_banlists=False)
    manager.load_banlist(SINGLE_BANLIST_PATH)
    assert len(manager.banlists) == 1
    assert manager.banlists[0].name == "2024.12 TCG"
    assert not manager.banlists[0].whitelist
    assert len(manager.banlists[0].content) > 0
    assert manager.banlists[0].content[43262273] == 0
    assert manager.banlists[0].content[92107604] == 2
    assert manager.banlists[0].hash == TCG_BANLIST_HASH

def test_load_all_banlists():
    # this should basically also add the no limits banlist which is in memory
    manager = banlists.BanlistManager(BANLIST_FOLDER, load_banlists=False)
    manager.load_all_banlists()
    assert len(manager.banlists) == 2
    assert manager.banlists[0].name == "2024.12 TCG"
    assert manager.banlists[1].name == "No limits"
    assert not manager.banlists[0].whitelist
    assert not manager.banlists[1].whitelist
    assert len(manager.banlists[0].content) > 0
    assert len(manager.banlists[1].content) == 0
    assert manager.banlists[1].content == {}


def test_load_all_banlists_accepts_direct_lflist_file(tmp_path):
    lflist = tmp_path / "lflist.conf"
    lflist.write_text(
        "#[Old]\n"
        "!2025.4 TCG\n"
        "21044178 0\n"
        "34124316 2\n"
        "!2024.12 TCG\n"
        "43262273 0\n",
        encoding="utf-8",
    )

    manager = banlists.BanlistManager(lflist, load_banlists=False)
    manager.load_all_banlists()

    assert [banlist.name for banlist in manager.banlists] == ["2025.4 TCG", "2024.12 TCG", "No limits"]
    assert manager.banlists[0].content[21044178] == 0
    assert manager.banlists[0].content[34124316] == 2


def test_reload_replaces_existing_banlists(tmp_path):
    manager = banlists.BanlistManager(BANLIST_FOLDER, load_banlists=False)
    manager.banlists = [banlists.Banlist()]

    loaded = manager.reload(BANLIST_FOLDER)

    assert loaded is manager.banlists
    assert [banlist.name for banlist in manager.banlists] == ["2024.12 TCG", "No limits"]


def test_reload_restores_default_path_when_missing(mocker):
    manager = banlists.BanlistManager(load_banlists=False)
    manager.banlists_path = None
    load_all = mocker.patch.object(manager, "load_all_banlists")

    manager.reload()

    assert "sync" in str(manager.banlists_path)
    load_all.assert_called_once()

def test_get_limit_success():
    manager = banlists.BanlistManager(BANLIST_FOLDER)
    manager.load_all_banlists()
    assert manager.banlists[0].get_limit(43262273) == 0

def test_banlist_is_deck_allowed_success():
    manager = banlists.BanlistManager(BANLIST_FOLDER)
    manager.load_all_banlists()
    cards = [123456789]
    deck = Deck(cards, cards, "json")
    assert manager.banlists[1].is_deck_allowed(deck) == (True, {})


def test_banlist_is_deck_allowed_fail():
    manager = banlists.BanlistManager(BANLIST_FOLDER)
    manager.load_all_banlists()
    cards = [43262273, 43262273, 43262273]
    deck = Deck(cards, cards, "json")
    result, reason = manager.banlists[0].is_deck_allowed(deck)
    assert not result
    print(reason)
    assert 43262273 in reason.keys()
    assert reason[43262273].limit == 0
    assert reason[43262273].found == 6 # main + side

def test_is_deck_allowed_with_limited_cards():
    manager = banlists.BanlistManager(BANLIST_FOLDER)
    manager.load_all_banlists()
    cards = [34124316, 34124316] # 2 is the limit
    deck = Deck(cards, [], "json")
    result, reason = manager.banlists[0].is_deck_allowed(deck)
    assert result
    assert reason == {}
    cards = [34124316, 34124316, 34124316] # 2 is the limit
    deck = Deck(cards, [], "json")
    result, reason = manager.banlists[0].is_deck_allowed(deck)
    assert not result
    assert 34124316 in reason.keys()
    assert reason[34124316].limit == 2
    assert reason[34124316].found == 3 # main


def test_is_deck_allowed_counts_aliases_together(mocker):
    banlist = banlists.Banlist()
    banlist.content = {100: 1}

    db = mocker.MagicMock()
    def execute(sql, args=()):
        cursor = mocker.MagicMock()
        if sql.startswith("SELECT alias"):
            aliases = {100: 0, 101: 100}
            cursor.fetchone.return_value = [aliases.get(args[0], 0)]
        else:
            cursor.fetchall.return_value = [[100], [101]]
        return cursor
    db.execute.side_effect = execute
    language_handler = mocker.MagicMock()
    language_handler.primary_database = db
    mocker.patch("game.edo.banlists.variables.LANGUAGE_HANDLER", language_handler)

    result, reason = banlist.is_deck_allowed(Deck([100, 101], [], "json"))

    assert not result
    assert reason[100].limit == 1
    assert reason[100].found == 2


def test_banlist_remaining_fallbacks_and_invalid_lines(mocker, tmp_path):
    banlist = banlists.Banlist()
    assert banlist.get_limit(999) == 3
    assert banlist.is_deck_allowed(Deck([1], [], "json")) == (True, {})

    mocker.patch("game.edo.banlists.variables.LANGUAGE_HANDLER", object())
    assert banlist._get_alias_group(123) == {123}

    db = mocker.MagicMock()
    db.execute.side_effect = RuntimeError("db down")
    handler = mocker.MagicMock(primary_database=db)
    mocker.patch("game.edo.banlists.variables.LANGUAGE_HANDLER", handler)
    assert banlist._get_alias_group(456) == {456}
    assert banlist._get_limited_code({456}) is None

    manager = banlists.BanlistManager(tmp_path, load_banlists=False)
    manager.banlists = []
    conf = tmp_path / "edge.conf"
    conf.write_text(
        "# ignored\n"
        "\n"
        "!Edge\n"
        "$whitelist\n"
        "missinglimit\n"
        "abc 1\n"
        "0 1\n"
        "10 -40\n"
        "20 40\n",
        encoding="utf-8",
    )
    manager.load_banlist(conf)
    assert manager.banlists[0].whitelist is True
    assert manager.banlists[0].content[10] == -40
    assert manager.banlists[0].content[20] == 40
    assert manager.get_banlist_names() == ["Edge"]
    assert manager.get_banlist_by_name("Edge") is manager.banlists[0]
    assert manager.get_banlist_by_name("missing") is None
    assert manager.get_banlist_by_hash(123456) is None

    banlists.BanlistManager._instance = None
    default_manager = banlists.BanlistManager(load_banlists=False)
    assert "sync" in str(default_manager.banlists_path)

    banlist = banlists.Banlist()
    banlist.content = {999: 1}
    result, reason = banlist.is_deck_allowed(Deck([123], [], "json"))
    assert result is True
    assert reason == {}
