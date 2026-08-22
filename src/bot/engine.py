import json
import logging
import os
import pathlib
import platform

logger = logging.getLogger(__name__)

_initialized = False
_bot_initialized = False
_native_dll_directory_handles = []


def ensure_runtime():
    """Load .NET 6 CoreCLR runtime via pythonnet. Call once at app startup."""
    global _initialized
    if _initialized:
        return
    from pythonnet import load
    load("coreclr")
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
    for db in db_paths:
        WB.AddDatabase(db)
    _bot_initialized = True
    logger.info("WindBot engine initialized with %d databases", len(db_paths))


def launch_bot(host: str, port: int, room_info: str, deck: str = "",
               name: str = "WindBot", hand: int = 0, chat: bool = True,
               version: int = 0):
    """Launch a bot instance that connects to the given server via TCP.

    The bot runs in its own .NET thread — this function returns immediately.
    """
    if not _bot_initialized:
        raise RuntimeError("Bot engine not initialized. Call init_bot() first.")

    from WindBot import WindBot as WB

    launch_data = json.dumps({
        "Name": name,
        "Deck": deck,
        "Host": host,
        "Port": str(port),
        "HostInfo": room_info,
        "Version": str(version),
        "Hand": str(hand),
        "Chat": "1" if chat else "0",
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
