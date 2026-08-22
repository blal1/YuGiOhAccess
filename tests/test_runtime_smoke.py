import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_offline_server_engine_room_api_and_lobby_socket():
    from core import variables
    from game.serverinfo import EdoServerInformation
    from server import embedded
    from server.engine_config import resolve_engine_paths

    variables.LOCAL_DATA_DIR = Path("src/data")
    lobby_port = _free_port()
    http_port = _free_port()
    paths = resolve_engine_paths()

    embedded.start_local_server(
        lobby_port=lobby_port,
        http_port=http_port,
        ocgcore_path=paths.ocgcore_path,
        db_paths=paths.db_paths,
        script_dir=paths.script_dir,
    )
    try:
        deadline = time.time() + 8
        room_payload = None
        while time.time() < deadline:
            try:
                response = requests.get(f"http://127.0.0.1:{http_port}/api/getrooms", timeout=1)
                response.raise_for_status()
                room_payload = response.json()
                break
            except Exception:
                time.sleep(0.2)

        assert room_payload == {"rooms": []}
        status = embedded.engine_status()
        assert status.available is True
        assert status.version == (11, 0)
        assert status.db_count > 0

        server = EdoServerInformation("Local smoke", "127.0.0.1", http_port, lobby_port)
        assert server.is_available(None) is True
        assert server.list_rooms() == []
    finally:
        embedded.stop_local_server()

    assert embedded.is_running() is False


def test_bot_assets_include_runtime_dependencies():
    from core import variables
    from bot import launcher

    variables.LOCAL_DATA_DIR = Path("src/data")
    asset_path = launcher._find_bot_asset_path()

    assert (asset_path / "WindBot.Desktop.dll").exists()
    assert (asset_path / "WindBot.Desktop.deps.json").exists()
    assert (asset_path / "Microsoft.Data.Sqlite.dll").exists()
    assert (asset_path / "SQLitePCLRaw.core.dll").exists()
    assert (asset_path / "SQLitePCLRaw.provider.e_sqlite3.dll").exists()
    assert any((asset_path / "runtimes").rglob("e_sqlite3.dll"))


def test_bot_engine_initializes_in_subprocess_without_database_load_errors():
    code = r"""
from pathlib import Path
from core import variables
variables.LOCAL_DATA_DIR = Path('src/data')
from bot import launcher
launcher._ensure_engine()
print('bot_ready')
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode == 0, combined_output
    assert "bot_ready" in combined_output
    assert "Failed loading database" not in combined_output
