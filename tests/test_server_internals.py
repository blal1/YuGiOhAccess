"""The parts of the server that are pure logic, and were never exercised.

The ocgcore wrapper needs a real shared library for most of what it does, but
its card database, its architecture check and its callbacks do not. Nor does
the prompt summariser, which exists to answer "did the bot have anything to
do, or did it not understand what it was offered?".
"""

import ctypes
import sqlite3
import struct

import pytest

from game.edo.message_constants import MSG_SELECT_BATTLECMD, MSG_SELECT_IDLECMD


# ------------------------------------------------------------ card database --

def _database(tmp_path, rows):
    path = tmp_path / "cards.cdb"
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE datas (id INTEGER, ot INTEGER, alias INTEGER, setcode INTEGER, "
        "type INTEGER, atk INTEGER, def INTEGER, level INTEGER, race INTEGER, "
        "attribute INTEGER, category INTEGER)"
    )
    connection.executemany("INSERT INTO datas VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    connection.commit()
    connection.close()
    return str(path)


def test_a_card_is_read_back_with_its_level_and_scales(tmp_path):
    from server.core import CardDatabase

    # level packs the pendulum scales into its upper bytes.
    level = (3 << 24) | (5 << 16) | 4
    path = _database(tmp_path, [(1, 0, 0, 0x1234, 0x21, 1800, 1200, level, 0x10, 0x20, 0)])

    database = CardDatabase([path])
    card = database.get_card(1)

    assert card["level"] == 4
    assert (card["lscale"], card["rscale"]) == (3, 5)
    assert (card["attack"], card["defense"]) == (1800, 1200)
    assert card["setcodes"] == [0x1234]


def test_a_link_monster_keeps_its_markers_where_its_defense_would_be(tmp_path):
    from server.core import CardDatabase

    link_type = 0x4000000 | 0x1
    path = _database(tmp_path, [(2, 0, 0, 0, link_type, 2000, 0o0005, 1, 0, 0, 0)])

    card = CardDatabase([path]).get_card(2)

    assert card["link_marker"] == 0o0005


def test_a_card_nobody_has_heard_of_reads_back_as_nothing(tmp_path):
    from server.core import CardDatabase

    database = CardDatabase([_database(tmp_path, [])])

    assert database.get_card(999) is None
    assert database.get_type(999) == 0


def test_a_database_that_will_not_open_does_not_stop_the_others(tmp_path, caplog):
    from server.core import CardDatabase

    good = _database(tmp_path, [(1, 0, 0, 0, 0x1, 100, 100, 1, 0, 0, 0)])
    broken = tmp_path / "broken.cdb"
    broken.write_bytes(b"not a database")

    with caplog.at_level("ERROR", logger="server.core"):
        database = CardDatabase([str(broken), good])

    assert database.get_card(1) is not None
    assert "Failed to load" in caplog.text


def test_setcodes_are_unpacked_into_a_null_terminated_list():
    from server.core import CardDatabase

    packed = 0x1111 | (0x2222 << 16) | (0x3333 << 32)

    assert CardDatabase._parse_setcodes(packed) == [0x1111, 0x2222, 0x3333]
    assert CardDatabase._parse_setcodes(0) == []


# ------------------------------------------------- the architecture check ----

def _pe_file(tmp_path, machine):
    """The smallest thing that looks like a PE image to the header reader."""
    path = tmp_path / "fake.dll"
    header = bytearray(64)
    header[0:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 64)
    pe = b"PE\0\0" + struct.pack("<H", machine)
    path.write_bytes(bytes(header) + pe)
    return path


def test_the_architecture_of_a_library_is_read_from_its_header(tmp_path):
    from server.core import _read_pe_machine

    assert _read_pe_machine(_pe_file(tmp_path, 0x8664)) == 0x8664
    assert _read_pe_machine(_pe_file(tmp_path, 0x014C)) == 0x014C


def test_something_that_is_not_a_library_reads_as_unknown(tmp_path):
    from server.core import _read_pe_machine

    not_pe = tmp_path / "text.dll"
    not_pe.write_bytes(b"just some text, definitely not a PE image" * 4)

    assert _read_pe_machine(not_pe) is None
    assert _read_pe_machine(tmp_path / "missing.dll") is None


def test_a_32_bit_library_is_refused_by_64_bit_python(tmp_path, mocker):
    """The error a player gets is otherwise a bare OSError from the loader."""
    from server import core

    mocker.patch("server.core.struct.calcsize", return_value=8)  # 64-bit python

    with pytest.raises(OSError, match="architecture mismatch"):
        core._validate_windows_library_architecture(_pe_file(tmp_path, 0x014C))


def test_a_matching_library_passes(tmp_path, mocker):
    from server import core

    mocker.patch("server.core.struct.calcsize", return_value=8)

    core._validate_windows_library_architecture(_pe_file(tmp_path, 0x8664))
    core._validate_windows_library_architecture(_pe_file(tmp_path, 0xAA64))


def test_an_unrecognised_machine_is_left_alone(tmp_path, mocker):
    from server import core

    mocker.patch("server.core.struct.calcsize", return_value=8)

    core._validate_windows_library_architecture(_pe_file(tmp_path, 0x1234))


# ------------------------------------------------------ prompt summaries ----

def _card_entry(code, sequence_bytes=4, extra=False):
    entry = struct.pack("<I", code) + bytes([0, 0x04])
    entry += struct.pack("<I", 0) if sequence_bytes == 4 else bytes([0])
    if extra:
        entry += struct.pack("<Q", 0) + bytes([0])
    return entry


def test_an_idle_prompt_says_what_it_is_offering():
    from server import prompt_debug

    body = bytes([MSG_SELECT_IDLECMD, 0])
    body += struct.pack("<I", 1) + _card_entry(0x1234)          # summonable
    body += struct.pack("<I", 0)                                 # special summonable
    body += struct.pack("<I", 0)                                 # repositionable
    body += struct.pack("<I", 0)                                 # monster settable
    body += struct.pack("<I", 0)                                 # spell settable
    body += struct.pack("<I", 1) + _card_entry(0x5678, extra=True)  # activatable
    body += bytes([1, 1])                                        # battle phase, end turn

    summary = prompt_debug.summarise(MSG_SELECT_IDLECMD, body)

    assert "summonable=['0x1234']" in summary
    assert "activatable=['0x5678']" in summary
    assert "can enter battle phase" in summary
    assert "can end turn" in summary


def test_an_idle_prompt_that_offers_nothing_says_so():
    from server import prompt_debug

    body = bytes([MSG_SELECT_IDLECMD, 0]) + struct.pack("<I", 0) * 6 + bytes([0, 0])

    assert prompt_debug.summarise(MSG_SELECT_IDLECMD, body) == "nothing at all"


def test_a_battle_prompt_lists_who_can_attack():
    from server import prompt_debug

    body = bytes([MSG_SELECT_BATTLECMD, 0])
    body += struct.pack("<I", 0)  # activatable
    body += struct.pack("<I", 1) + struct.pack("<I", 0x9999) + bytes([0, 0x04, 0, 1])
    body += bytes([1, 1])

    summary = prompt_debug.summarise(MSG_SELECT_BATTLECMD, body)

    assert "can attack=['0x9999']" in summary
    assert "can enter main phase 2" in summary


def test_a_prompt_that_cannot_be_summarised_is_not_an_error():
    from server import prompt_debug

    assert prompt_debug.summarise(MSG_SELECT_IDLECMD, b"\x0b") is None
    # Anything that is not one of the two prompts it knows about.
    assert prompt_debug.summarise(99, b"\x63\x00") is None


# ------------------------------------------------------- deck error wording --

@pytest.mark.parametrize("error,expected", [
    (("MAINCOUNT", 39, 40, 60, 0), "main deck has 39 cards"),
    (("EXTRACOUNT", 16, 0, 15, 0), "extra deck has 16 cards"),
    (("SIDECOUNT", 16, 0, 15, 0), "side deck has 16 cards"),
    (("UNKNOWNCARD", 0, 0, 0, 42), "card 42 is not in the card database"),
    (("LFLIST", 2, 0, 1, 7), "banlist allows 1"),
    (("CARDCOUNT", 4, 0, 3, 7), "at most 3 allowed"),
])
def test_every_deck_error_has_words_for_the_log(error, expected):
    from server import deck_check

    name, got, minimum, maximum, code = error
    kind = getattr(deck_check, f"DECKERROR_{name}")
    described = deck_check.describe(
        deck_check.DeckError(kind, got=got, minimum=minimum, maximum=maximum, code=code)
    )

    assert expected in described


def test_an_unknown_deck_error_still_describes_itself():
    from server import deck_check

    assert "deck error 99" in deck_check.describe(deck_check.DeckError(99))


def test_a_banlist_that_throws_falls_back_to_three_copies():
    from server import deck_check

    class Broken:
        def get_limit(self, code):
            raise RuntimeError("no banlist here")

    deck = [7, 7, 7, 7] + list(range(100, 136))
    error = deck_check.check_deck(deck, [], [], banlist=Broken())

    assert error.type == deck_check.DECKERROR_CARDCOUNT
    assert error.maximum == 3


def test_the_deck_error_struct_is_the_size_the_client_expects():
    from game.edo import structs
    from server import deck_check

    raw = deck_check.DeckError(deck_check.DECKERROR_SIDECOUNT, got=20, maximum=15).to_bytes()

    assert len(raw) == ctypes.sizeof(structs.DeckErrrorMSG)
