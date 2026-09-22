"""The in duel history: what happened and what the player chose, in one list."""

import pytest

from core import speech, utils
from ui import duel_history_ui


@pytest.fixture(autouse=True)
def clean_log():
    speech.MESSAGE_LOG.clear()
    yield
    speech.MESSAGE_LOG.clear()


def test_actions_and_messages_share_one_stream_in_order():
    speech.MESSAGE_LOG.add("Your opponent drew 1 card")
    utils.record_action("Normal summon Blue-Eyes White Dragon")
    speech.MESSAGE_LOG.add("Blue-Eyes White Dragon was summoned")

    kinds = [entry.kind for entry in speech.MESSAGE_LOG.entries()]
    texts = [entry.text for entry in speech.MESSAGE_LOG.entries()]

    assert kinds == [speech.Kind.MESSAGE, speech.Kind.ACTION, speech.Kind.MESSAGE]
    assert texts[1] == "Normal summon Blue-Eyes White Dragon"


def test_the_spoken_replay_leaves_out_the_players_own_choices():
    utils.record_action("End turn")
    speech.MESSAGE_LOG.add("New turn for player 1")

    assert speech.MESSAGE_LOG.recent() == ["New turn for player 1"]


def test_catch_up_does_not_read_back_actions():
    utils.record_action("Attack with Blue-Eyes")
    speech.MESSAGE_LOG.add("Something you missed", spoken=False)

    assert speech.MESSAGE_LOG.missed() == ["Something you missed"]


def test_an_empty_action_is_not_recorded():
    utils.record_action("   ")

    assert speech.MESSAGE_LOG.entries() == []


def test_lines_are_stamped_from_the_start_of_the_duel():
    speech.MESSAGE_LOG.add("First thing")
    entries = speech.MESSAGE_LOG.entries()
    started_at = entries[0].at

    line = duel_history_ui.format_entry(entries[0], started_at)

    assert line.startswith("00:00")
    assert "First thing" in line


def test_a_players_own_choice_is_marked_as_theirs():
    utils.record_action("Set a card")
    entry = speech.MESSAGE_LOG.entries()[0]

    line = duel_history_ui.format_entry(entry, entry.at)

    assert "You" in line
    assert "Set a card" in line


def test_elapsed_time_is_minutes_and_seconds():
    speech.MESSAGE_LOG.add("Later on")
    entry = speech.MESSAGE_LOG.entries()[0]

    line = duel_history_ui.format_entry(entry, entry.at - 75)

    assert line.startswith("01:15")


def test_history_lines_are_oldest_first():
    speech.MESSAGE_LOG.add("One")
    utils.record_action("Two")
    speech.MESSAGE_LOG.add("Three")

    lines = duel_history_ui.history_lines()

    assert [line.split(" ", 1)[1] for line in lines] == ["One", "You: Two", "Three"]


def test_an_empty_history_has_no_lines():
    assert duel_history_ui.history_lines() == []


def test_the_log_holds_a_whole_duel():
    for i in range(speech.HISTORY_CAPACITY + 10):
        speech.MESSAGE_LOG.add(f"message {i}")

    entries = speech.MESSAGE_LOG.entries()
    assert len(entries) == speech.HISTORY_CAPACITY
    assert speech.HISTORY_CAPACITY >= 500


def test_copying_survives_a_refused_clipboard(mocker):
    mocker.patch.object(duel_history_ui.wx, "TheClipboard", **{"Open.return_value": False})

    assert duel_history_ui.copy_history_to_clipboard(["a line"]) is False


def test_copying_an_empty_history_does_nothing():
    assert duel_history_ui.copy_history_to_clipboard([]) is False
