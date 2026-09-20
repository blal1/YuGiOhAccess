"""Tests for the screen reader message log, priorities and catch-up handling."""

import struct
from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def clean_speech_state():
    from core import speech

    speech.MESSAGE_LOG.clear()
    speech.CATCH_UP.finish()
    yield
    speech.MESSAGE_LOG.clear()
    speech.CATCH_UP.finish()


def _app(mocker, active=True):
    """Patch wx so utils.output sees a window that is (or is not) focused."""
    app = MagicMock()
    app.IsActive.return_value = active
    frame = MagicMock()
    mocker.patch("core.utils.wx.GetApp", return_value=app)
    mocker.patch("core.utils.wx.GetTopLevelWindows", return_value=[frame])
    return frame


def test_message_is_spoken_and_logged_when_focused(mocker):
    from core import speech, utils

    frame = _app(mocker)
    utils.output("Attack declared")

    frame.output.assert_called_once_with("Attack declared", False)
    assert speech.MESSAGE_LOG.recent() == ["Attack declared"]


def test_unfocused_messages_are_logged_instead_of_dropped(mocker):
    from core import speech, utils

    frame = _app(mocker, active=False)
    utils.output("Opponent summons Blue-Eyes")

    frame.output.assert_not_called()
    assert speech.MESSAGE_LOG.recent() == ["Opponent summons Blue-Eyes"]
    assert speech.MESSAGE_LOG.missed() == ["Opponent summons Blue-Eyes"]


def test_critical_messages_interrupt(mocker):
    from core import speech, utils

    frame = _app(mocker)
    utils.output("Direct attack", priority=speech.Priority.CRITICAL)
    frame.output.assert_called_once_with("Direct attack", True)


def test_ambient_messages_step_aside_for_a_critical_one(mocker):
    from core import speech, utils

    frame = _app(mocker)
    utils.output("You take 3000 damage", priority=speech.Priority.CRITICAL)
    frame.output.reset_mock()

    utils.output("Entering main phase 2", priority=speech.Priority.AMBIENT)
    frame.output.assert_not_called()
    # It is still recorded, so the replay key can read it back.
    assert "Entering main phase 2" in speech.MESSAGE_LOG.recent()
    assert "Entering main phase 2" in speech.MESSAGE_LOG.missed()


def test_ambient_messages_are_spoken_once_the_window_has_passed(mocker):
    from core import speech, utils

    frame = _app(mocker)
    mocker.patch.object(speech.MESSAGE_LOG, "critical_recently_spoken", return_value=False)
    utils.output("Entering end phase", priority=speech.Priority.AMBIENT)
    frame.output.assert_called_once_with("Entering end phase", False)


def test_info_messages_are_not_suppressed_by_a_critical_one(mocker):
    from core import speech, utils

    frame = _app(mocker)
    utils.output("Direct attack", priority=speech.Priority.CRITICAL)
    frame.output.reset_mock()
    utils.output("Card drawn", priority=speech.Priority.INFO)
    frame.output.assert_called_once_with("Card drawn", False)


def test_replay_reads_back_the_last_messages(mocker):
    from core import utils

    frame = _app(mocker)
    for index in range(15):
        utils.output(f"message {index}")
    frame.output.reset_mock()

    text = utils.replay_recent_messages(10)
    assert text.splitlines() == [f"message {index}" for index in range(5, 15)]
    frame.output.assert_called_once_with(text, True)


def test_replay_with_an_empty_log(mocker):
    from core import utils

    _app(mocker)
    assert "No messages to replay." in utils.replay_recent_messages()


def test_replay_does_not_pollute_the_log(mocker):
    from core import speech, utils

    _app(mocker)
    utils.output("one")
    utils.replay_recent_messages()
    assert speech.MESSAGE_LOG.recent() == ["one"]


def test_the_log_is_bounded():
    from core.speech import MessageLog

    log = MessageLog(capacity=3)
    for index in range(10):
        log.add(f"m{index}")
    assert len(log) == 3
    assert log.recent(10) == ["m7", "m8", "m9"]


def test_catch_up_suppresses_the_burst_and_counts_it(mocker):
    from core import speech, utils

    frame = _app(mocker)
    speech.CATCH_UP.start()
    for index in range(50):
        utils.output(f"replayed {index}", priority=speech.Priority.CRITICAL)

    frame.output.assert_not_called()
    assert speech.CATCH_UP.finish() == 50
    assert speech.MESSAGE_LOG.recent(3) == ["replayed 47", "replayed 48", "replayed 49"]


def test_catchup_packet_announces_start_and_summary(mocker):
    import ui
    from core import speech, utils

    mocker.patch("core.utils.output")
    client = MagicMock()

    ui.handle_catchup(client, b"\x01", 1)
    assert speech.CATCH_UP.active is True
    assert client.memory.catching_up is True
    assert any("Catching up" in call.args[0] for call in utils.output.call_args_list)

    speech.CATCH_UP.note_suppressed()
    speech.CATCH_UP.note_suppressed()

    ui.handle_catchup(client, b"\x00", 1)
    assert speech.CATCH_UP.active is False
    assert client.memory.catching_up is False
    assert any("2 message(s) were skipped" in call.args[0] for call in utils.output.call_args_list)


def test_catchup_finishing_with_nothing_skipped(mocker):
    import ui
    from core import utils

    mocker.patch("core.utils.output")
    client = MagicMock()
    ui.handle_catchup(client, b"\x00", 1)
    assert any("Caught up with the duel." in call.args[0] for call in utils.output.call_args_list)


def test_watch_change_reports_the_spectator_count(mocker):
    import ui
    from core import utils
    from game.edo import structs

    mocker.patch("core.utils.output")
    client = MagicMock()
    client.memory = MagicMock()
    client.memory.watch_count = None

    payload = struct.pack("<H", 3)
    ui.handle_watch_change(client, payload, len(payload))
    assert client.memory.watch_count == 3
    assert any("3 spectator(s) watching." in call.args[0] for call in utils.output.call_args_list)

    # Repeating the same count does not repeat the announcement.
    utils.output.reset_mock()
    ui.handle_watch_change(client, payload, len(payload))
    utils.output.assert_not_called()

    # WATCH_CHANGE and CATCHUP were declared in structs.py with no handler.
    assert structs.ServerIdType.WATCH_CHANGE in utils.packet_handlers
    assert structs.ServerIdType.CATCHUP in utils.packet_handlers


def test_watch_change_ignores_a_short_packet(mocker):
    import ui
    from core import utils

    mocker.patch("core.utils.output")
    client = MagicMock()
    ui.handle_watch_change(client, b"", 0)
    utils.output.assert_not_called()


def test_output_is_safe_without_a_wx_app(mocker):
    from core import speech, utils

    mocker.patch("core.utils.wx.GetApp", return_value=None)
    utils.output("headless")
    assert speech.MESSAGE_LOG.recent() == ["headless"]
