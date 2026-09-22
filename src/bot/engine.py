import json
import logging
import os
import pathlib
import platform
import threading
import time

logger = logging.getLogger(__name__)
bot_logger = logging.getLogger("windbot")

_initialized = False
_bot_initialized = False
_native_dll_directory_handles: list = []
_console_pump = None


class DotNetMissing(RuntimeError):
    """The .NET runtime the bot needs is not installed."""


def ensure_runtime():
    """Load the .NET runtime through pythonnet. Call once at app startup.

    The runtime is not bundled: a packaged build carries WindBot's assembly
    but relies on .NET being installed on the machine. When it is not, the
    failure from pythonnet says nothing a player could act on, so it is
    translated into something that names the missing piece.
    """
    global _initialized
    if _initialized:
        return
    from pythonnet import load

    try:
        load("coreclr")
    except Exception as error:
        logger.error("Could not load the .NET runtime: %s", error)
        raise DotNetMissing(
            "The bot needs the .NET runtime, which does not appear to be "
            "installed. Install the .NET 6 (or newer) runtime from "
            "https://dotnet.microsoft.com/download and try again."
        ) from error
    _initialized = True


def init_bot(asset_path: str, db_paths: list[str]):
    """Initialize WindBot engine: load card databases and deck definitions."""
    global _bot_initialized
    if _bot_initialized:
        return
    asset_path = str(pathlib.Path(asset_path).resolve())
    bot_dll = pathlib.Path(asset_path) / "WindBot.Desktop.dll"
    if not bot_dll.exists():
        raise FileNotFoundError(f"WindBot engine DLL not found: {bot_dll}")
    _add_native_dependency_dirs(pathlib.Path(asset_path))
    ensure_runtime()
    import clr
    clr.AddReference(str(bot_dll))
    from WindBot import WindBot as WB
    WB.InitAndroid(asset_path)
    capture_bot_console()
    loaded = 0
    for db in db_paths:
        try:
            WB.AddDatabase(db)
            loaded += 1
        except Exception:
            logger.exception("The bot could not load card database %s", db)
    logger.info("WindBot card databases: %d of %d loaded", loaded, len(db_paths))
    _bot_initialized = True


def capture_bot_console():
    """Send the bot's own log into ours.

    WindBot runs in this process and writes to the .NET console, which a
    windowed application throws away. That console is the only place the bot
    says what it decided and why, so without this a bot that quietly does
    nothing leaves no trace at all.
    """
    global _console_pump
    if _console_pump is not None:
        return
    try:
        from System import Console
        from System.IO import StringWriter
        from System.Text import StringBuilder
    except Exception:
        logger.debug("No .NET console to capture", exc_info=True)
        return

    builder = StringBuilder()
    writer = StringWriter(builder)
    Console.SetOut(writer)
    Console.SetError(writer)

    def pump():
        while True:
            time.sleep(0.5)
            try:
                if builder.Length == 0:
                    continue
                text = builder.ToString()
                builder.Clear()
            except Exception:
                logger.debug("Bot console pump stopped", exc_info=True)
                return
            for line in text.splitlines():
                line = line.strip()
                if line:
                    bot_logger.info("%s", line)

    _console_pump = threading.Thread(target=pump, name="windbot-console", daemon=True)
    _console_pump.start()
    logger.info("Capturing WindBot console output into the application log")


def launch_bot(host: str, port: int, room_info: str, deck: str = "",
               name: str = "WindBot", hand: int = 0, chat: bool = True,
               version: int = 0, debug: bool | None = None):
    """Launch a bot instance that connects to the given server via TCP.

    The bot runs in its own .NET thread — this function returns immediately.
    """
    if not _bot_initialized:
        raise RuntimeError("Bot engine not initialized. Call init_bot() first.")

    from WindBot import WindBot as WB

    if debug is None:
        from core import variables

        debug = bool(getattr(variables, "DEBUG_MODE", False))
    launch_data = json.dumps({
        "Name": str(name),
        "Deck": str(deck),
        "Host": str(host),
        "Port": str(port),
        # Every field of WindBot's launch payload is typed as a string. A room
        # id passed as a number makes the whole payload fail to deserialise,
        # and the bot then falls back to its defaults: wrong host, wrong deck.
        "HostInfo": str(room_info),
        "Version": str(version),
        "Hand": str(hand),
        "Chat": "1" if chat else "0",
        # Makes WindBot narrate its reasoning, which capture_bot_console picks up.
        "Debug": "1" if debug else "0",
    })
    WB.RunAndroid(launch_data)
    logger.info("Bot '%s' launched (deck=%s, target=%s:%d)", name, deck or "random", host, port)


def _add_native_dependency_dirs(asset_path: pathlib.Path):
    if platform.system() != "Windows":
        return
    arch = platform.machine().lower()
    if arch in ("amd64", "x86_64"):
        rid = "win-x64"
    elif arch in ("arm64", "aarch64"):
        rid = "win-arm64"
    else:
        rid = "win-x86"
    native_dir = asset_path / "runtimes" / rid / "native"
    if native_dir.exists():
        native_dir_str = str(native_dir)
        os.environ["PATH"] = native_dir_str + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            _native_dll_directory_handles.append(os.add_dll_directory(native_dir_str))
