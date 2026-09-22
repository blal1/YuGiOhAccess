"""Running the server on its own, with `python -m server`.

This entry point had no tests at all, which is how it kept working by luck:
it is the only way to run the server without the client, and the only thing
that reads its command line.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _fake_server(mocker):
    """A lobby or room API whose start and stop can both be awaited."""
    server = MagicMock()
    server.start = mocker.AsyncMock()
    server.stop = mocker.AsyncMock()
    return server


def _args(**overrides):
    defaults = dict(host="127.0.0.1", lobby_port=7933, http_port=7934,
                    ocgcore="", scripts="", db=[], debug=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _parsed_args(mocker, argv):
    """Run main() and hand back the arguments it would have served.

    The coroutine main() builds is closed rather than awaited, so it does not
    sit around unawaited and warn about it later.
    """
    from server import __main__ as entry

    captured = {}

    def capture(coro):
        captured["args"] = coro.cr_frame.f_locals.get("args")
        coro.close()

    mocker.patch("server.__main__.asyncio.run", side_effect=capture)
    mocker.patch("sys.argv", argv)
    entry.main()
    return captured["args"]


def test_the_command_line_has_sensible_defaults(mocker):
    args = _parsed_args(mocker, ["server"])

    assert args.host == "0.0.0.0"
    assert (args.lobby_port, args.http_port) == (7933, 7934)
    assert args.db == [] and args.debug is False


def test_the_ports_and_host_can_be_chosen(mocker):
    args = _parsed_args(mocker, [
        "server", "--host", "127.0.0.1", "--lobby-port", "1111",
        "--http-port", "2222", "--db", "one.cdb", "--db", "two.cdb", "--debug",
    ])

    assert args.host == "127.0.0.1"
    assert (args.lobby_port, args.http_port) == (1111, 2222)
    assert args.db == ["one.cdb", "two.cdb"]
    assert args.debug is True


def test_it_starts_the_lobby_and_the_room_api_without_an_engine(mocker, caplog):
    from server import __main__ as entry

    lobby = _fake_server(mocker)
    api = _fake_server(mocker)
    mocker.patch("server.lobby.LobbyServer", return_value=lobby)
    mocker.patch("server.room_api.RoomAPI", return_value=api)
    # Stop it before it waits forever. The interrupt is caught inside
    # run_server, which then shuts both halves down.
    mocker.patch("server.__main__.asyncio.Event", side_effect=KeyboardInterrupt)

    with caplog.at_level("WARNING", logger="server.__main__"):
        asyncio.run(entry.run_server(_args()))

    lobby.start.assert_awaited_once_with("127.0.0.1", 7933)
    api.start.assert_awaited_once_with("127.0.0.1", 7934)
    lobby.stop.assert_awaited_once()
    api.stop.assert_awaited_once()
    assert "ocgcore" in caplog.text


def test_it_loads_the_engine_when_one_is_given(mocker, tmp_path):
    from server import __main__ as entry

    core_file = tmp_path / "ocgcore.dll"
    core_file.write_bytes(b"fake")
    engine = MagicMock()
    engine.get_version.return_value = (10, 0)
    made = mocker.patch("server.core.OcgCore", return_value=engine)
    lobby = _fake_server(mocker)
    api = _fake_server(mocker)
    lobby_cls = mocker.patch("server.lobby.LobbyServer", return_value=lobby)
    mocker.patch("server.room_api.RoomAPI", return_value=api)
    mocker.patch("server.__main__.asyncio.Event", side_effect=KeyboardInterrupt)

    asyncio.run(entry.run_server(_args(ocgcore=str(core_file), db=["cards.cdb"], scripts="s")))

    made.assert_called_once_with(str(core_file), ["cards.cdb"], "s")
    assert lobby_cls.call_args.kwargs["duel_engine"] is engine


def test_a_missing_engine_path_stops_rather_than_starting_a_useless_server(mocker, tmp_path):
    from server import __main__ as entry

    with pytest.raises(SystemExit):
        asyncio.run(entry.run_server(_args(ocgcore=str(tmp_path / "nope.dll"))))
