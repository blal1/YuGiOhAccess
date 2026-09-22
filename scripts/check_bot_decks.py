"""Play a short duel with every bot deck and report which ones actually play.

The bot is only useful if its executor recognises the cards it draws. This runs
a real duel per deck through the bundled server against a scripted opponent that
always passes, so anything the bot does is its own doing, and reports whether it
ever did something other than pass.

    uv run python scripts/check_bot_decks.py            # every deck
    uv run python scripts/check_bot_decks.py Horus ABC  # just these
"""

import asyncio
import logging
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

from core import variables  # noqa: E402

variables.LOCAL_DATA_DIR = ROOT / "src" / "data"

from game.edo import default_values, structs, structs_utils  # noqa: E402
from game.edo.message_constants import (  # noqa: E402
    MSG_SELECT_BATTLECMD, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
    MSG_SELECT_EFFECTYN, MSG_SELECT_IDLECMD, MSG_SELECT_OPTION,
    MSG_SELECT_PLACE, MSG_SELECT_POSITION, MSG_SELECT_SUM,
    MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD, MSG_SELECT_YESNO,
    MSG_WIN,
)
from server.protocol import ClientPacket, ServerPacket, encode_packet  # noqa: E402

HOST = "127.0.0.1"
LOBBY_PORT = 7961
HTTP_PORT = 7962
DUEL_TIMEOUT = 30

# Idle responses: the low byte is the action. 7 ends the turn, and a chain
# answer of -1 declines. Anything else means the bot actually did something.
IDLE_END_TURN = 7
BATTLE_END_TURN = 3


def read_ydk(path):
    main, extra = [], []
    target = main
    for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("#extra"):
            target = extra
            continue
        if line.startswith("!side"):
            break
        if line.startswith(("#", "!")):
            continue
        if line.isdigit():
            target.append(int(line))
    return main, extra


class PassiveOpponent:
    """Hosts the room and passes on everything it is offered."""

    def __init__(self, deck):
        self.main, self.extra = deck
        self.room_id = None
        self.finished = asyncio.Event()
        self.started = False

    async def connect(self):
        reader, self.writer = await asyncio.open_connection(HOST, LOBBY_PORT)
        await self.send(ClientPacket.PLAYER_INFO,
                        bytes(structs_utils.string_to_u16("Opponent", 20)))
        host_info = structs.HostInfo.from_buffer_copy(bytes(default_values.HOST_INFO))
        host_info.t0_count = host_info.t1_count = host_info.best_of = 1
        await self.send(ClientPacket.CREATE_GAME, bytes(structs.CreateGame(
            host_info=host_info,
            name=structs_utils.string_to_u16("deck check", 20),
            password=structs_utils.string_to_u16("", 20),
            notes=b"",
        )))
        asyncio.create_task(self._listen(reader))
        for _ in range(100):
            if self.room_id is not None:
                return
            await asyncio.sleep(0.05)
        raise RuntimeError("the room was never created")

    async def send(self, packet_id, data=b""):
        self.writer.write(encode_packet(packet_id, data))
        await self.writer.drain()

    async def _listen(self, reader):
        while True:
            try:
                header = await reader.readexactly(2)
                body = await reader.readexactly(struct.unpack("<H", header)[0])
            except (asyncio.IncompleteReadError, ConnectionError):
                self.finished.set()
                return
            try:
                await self._on_packet(body[0], body[1:])
            except (ConnectionError, OSError):
                self.finished.set()
                return

    async def _on_packet(self, packet_id, payload):
        if packet_id == ServerPacket.CREATE_GAME:
            self.room_id = struct.unpack("<I", payload[:4])[0]
        elif packet_id == ServerPacket.JOIN_GAME:
            deck = struct.pack("<II", len(self.main) + len(self.extra), 0)
            for code in self.main + self.extra:
                deck += struct.pack("<I", code)
            await self.send(ClientPacket.UPDATE_DECK, deck)
            await self.send(ClientPacket.READY)
        elif packet_id == ServerPacket.PLAYER_ENTER and not self.started:
            self.started = True
            await asyncio.sleep(0.8)
            await self.send(ClientPacket.TRY_START)
        elif packet_id == ServerPacket.CHOOSE_RPS:
            await self.send(ClientPacket.RPS_CHOICE, bytes([2]))
        elif packet_id == ServerPacket.CHOOSE_ORDER:
            await self.send(ClientPacket.TURN_CHOICE, bytes([0]))  # bot goes first
        elif packet_id == ServerPacket.DUEL_END:
            self.finished.set()
        elif packet_id == ServerPacket.GAME_MSG:
            await self._on_duel_message(payload)

    async def _on_duel_message(self, data):
        kind = data[0]
        if kind == MSG_WIN:
            self.finished.set()
        elif kind == MSG_SELECT_IDLECMD:
            await self.send(ClientPacket.RESPONSE, struct.pack("<I", IDLE_END_TURN))
        elif kind == MSG_SELECT_BATTLECMD:
            await self.send(ClientPacket.RESPONSE, struct.pack("<I", BATTLE_END_TURN))
        elif kind == MSG_SELECT_CHAIN:
            await self.send(ClientPacket.RESPONSE, struct.pack("<i", -1))
        elif kind in (MSG_SELECT_EFFECTYN, MSG_SELECT_YESNO):
            await self.send(ClientPacket.RESPONSE, struct.pack("<I", 0))
        elif kind in (MSG_SELECT_OPTION, MSG_SELECT_PLACE, MSG_SELECT_POSITION):
            await self.send(ClientPacket.RESPONSE, struct.pack("<I", 0))
        elif kind in (MSG_SELECT_CARD, MSG_SELECT_TRIBUTE, MSG_SELECT_UNSELECT_CARD,
                      MSG_SELECT_SUM):
            await self.send(ClientPacket.RESPONSE,
                            struct.pack("<IIH", 1, 1, 0))


class BotWatcher(logging.Handler):
    """Counts what the bot was offered and how it answered."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.reset()

    def reset(self):
        self.prompts = 0
        self.actions = 0
        self.passes = 0
        self.errors = []
        # Only what the bot says once it is playing counts. Loading the card
        # databases happens once at startup and would otherwise be blamed on
        # whichever deck was checked first.
        self.playing = False

    def emit(self, record):
        message = record.getMessage()
        if record.name == "windbot":
            if not self.playing:
                return
            lowered = message.lower()
            if "error" in lowered or "exception" in lowered:
                self.errors.append(message.strip()[:160])
            return
        if message.startswith("Prompt "):
            self.playing = True
        if "Prompt SELECT_IDLECMD" in message or "Prompt SELECT_BATTLECMD" in message:
            self.prompts += 1
        elif "Response from WindBot" in message:
            payload = message.rsplit(": ", 1)[-1].strip()
            if payload in ("ffffffff",):
                self.passes += 1
                return
            try:
                value = int.from_bytes(bytes.fromhex(payload), "little")
            except ValueError:
                return
            action = value & 0xFFFF
            if action in (IDLE_END_TURN, BATTLE_END_TURN):
                self.passes += 1
            else:
                self.actions += 1


async def check_deck(deck_key, deck_file, watcher):
    from bot import engine

    watcher.reset()
    opponent = PassiveOpponent(read_ydk(ROOT / "src/data/bot/Decks" / f"{deck_file}.ydk"))
    await opponent.connect()
    engine.launch_bot(HOST, LOBBY_PORT, str(opponent.room_id), deck=deck_key,
                      name="WindBot", chat=False, debug=False)
    try:
        await asyncio.wait_for(opponent.finished.wait(), timeout=DUEL_TIMEOUT)
    except asyncio.TimeoutError:
        pass
    try:
        opponent.writer.close()
    except Exception:
        pass
    await asyncio.sleep(0.3)
    return watcher.prompts, watcher.actions, watcher.passes, list(watcher.errors)


async def main():
    from bot import deck_catalogue, engine
    from server import embedded
    from server.engine_config import resolve_engine_paths

    wanted = sys.argv[1:]
    decks = {k: v for k, v in deck_catalogue.KEY_TO_DECK_FILE.items()
             if not wanted or k in wanted}
    if not decks:
        print(f"No such deck. Known: {', '.join(sorted(deck_catalogue.KEY_TO_DECK_FILE))}")
        return 2

    paths = resolve_engine_paths()
    embedded.start_local_server(lobby_port=LOBBY_PORT, http_port=HTTP_PORT)
    await asyncio.sleep(1.5)
    if not embedded.engine_status().available:
        print(f"ocgcore unavailable: {embedded.engine_status().error}")
        return 2
    engine.init_bot(str(ROOT / "src/data/bot"), paths.db_paths)

    watcher = BotWatcher()
    for name in ("server.duel", "windbot"):
        watched = logging.getLogger(name)
        watched.addHandler(watcher)
        watched.setLevel(logging.INFO)
        # The watcher is the only consumer; the duel chatter must not reach the
        # console or the report drowns in it.
        watched.propagate = False

    silent, playing, broken = [], [], []
    print(f"{'deck':30} {'prompts':>8} {'actions':>8} {'passes':>7}  verdict")
    for key, deck_file in sorted(decks.items()):
        prompts, actions, passes, errors = await check_deck(key, deck_file, watcher)
        if errors:
            verdict = f"ERROR {errors[0][:60]}"
            broken.append(key)
        elif prompts == 0:
            verdict = "never got a turn"
            broken.append(key)
        elif actions == 0:
            verdict = "only ever passes"
            silent.append(key)
        else:
            verdict = "plays"
            playing.append(key)
        print(f"{key:30} {prompts:8} {actions:8} {passes:7}  {verdict}")

    print(f"\nplays: {len(playing)}   only passes: {len(silent)}   broken: {len(broken)}")
    if silent:
        print("only passes: " + ", ".join(silent))
    if broken:
        print("broken:      " + ", ".join(broken))
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
