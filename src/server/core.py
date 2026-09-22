"""ocgcore ctypes wrapper — loads the OCG duel engine shared library."""

import ctypes
import ctypes.util
import logging
import sqlite3
import struct
import sys
from pathlib import Path

logger = logging.getLogger(__name__)
_DLL_DIRECTORY_HANDLES: list = []

# --- Constants ---

LOCATION_DECK = 0x01
LOCATION_HAND = 0x02
LOCATION_MZONE = 0x04
LOCATION_SZONE = 0x08
LOCATION_GRAVE = 0x10
LOCATION_REMOVED = 0x20
LOCATION_EXTRA = 0x40
LOCATION_OVERLAY = 0x80
LOCATION_FZONE = 0x100
LOCATION_PZONE = 0x200

POS_FACEUP_ATTACK = 0x1
POS_FACEDOWN_ATTACK = 0x2
POS_FACEUP_DEFENSE = 0x4
POS_FACEDOWN_DEFENSE = 0x8

OCG_DUEL_STATUS_END = 0
OCG_DUEL_STATUS_AWAITING = 1
OCG_DUEL_STATUS_CONTINUE = 2

OCG_DUEL_CREATION_SUCCESS = 0


# --- ctypes struct definitions ---

class OCG_Player(ctypes.Structure):
    _fields_ = [
        ("startingLP", ctypes.c_uint32),
        ("startingDrawCount", ctypes.c_uint32),
        ("drawCountPerTurn", ctypes.c_uint32),
    ]


class OCG_CardData(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint32),
        ("alias", ctypes.c_uint32),
        ("setcodes", ctypes.POINTER(ctypes.c_uint16)),
        ("type", ctypes.c_uint32),
        ("level", ctypes.c_uint32),
        ("attribute", ctypes.c_uint32),
        ("race", ctypes.c_uint64),
        ("attack", ctypes.c_int32),
        ("defense", ctypes.c_int32),
        ("lscale", ctypes.c_uint32),
        ("rscale", ctypes.c_uint32),
        ("link_marker", ctypes.c_uint32),
    ]


# Callback types
OCG_DataReaderFunc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(OCG_CardData)
)
OCG_DataReaderDoneFunc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.POINTER(OCG_CardData)
)
OCG_ScriptReaderFunc = ctypes.CFUNCTYPE(
    ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p
)
OCG_LogHandlerFunc = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int
)


class OCG_DuelOptions(ctypes.Structure):
    _fields_ = [
        ("seed", ctypes.c_uint64 * 4),
        ("flags", ctypes.c_uint64),
        ("team1", OCG_Player),
        ("team2", OCG_Player),
        ("cardReader", OCG_DataReaderFunc),
        ("payload1", ctypes.c_void_p),
        ("scriptReader", OCG_ScriptReaderFunc),
        ("payload2", ctypes.c_void_p),
        ("logHandler", OCG_LogHandlerFunc),
        ("payload3", ctypes.c_void_p),
        ("cardReaderDone", OCG_DataReaderDoneFunc),
        ("payload4", ctypes.c_void_p),
        ("enableUnsafeLibraries", ctypes.c_uint8),
    ]


class OCG_NewCardInfo(ctypes.Structure):
    _fields_ = [
        ("team", ctypes.c_uint8),
        ("duelist", ctypes.c_uint8),
        ("code", ctypes.c_uint32),
        ("con", ctypes.c_uint8),
        ("loc", ctypes.c_uint32),
        ("seq", ctypes.c_uint32),
        ("pos", ctypes.c_uint32),
    ]


class OCG_QueryInfo(ctypes.Structure):
    _fields_ = [
        ("flags", ctypes.c_uint32),
        ("con", ctypes.c_uint8),
        ("loc", ctypes.c_uint32),
        ("seq", ctypes.c_uint32),
        ("overlay_seq", ctypes.c_uint32),
    ]


# --- Card Database ---

class CardDatabase:
    """Reads card data from SQLite .cdb files."""

    def __init__(self, db_paths: list[str]):
        self._cards: dict[int, dict] = {}
        for path in db_paths:
            self._load_db(path)
        logger.info("CardDatabase loaded %d cards from %d databases", len(self._cards), len(db_paths))

    def _load_db(self, path: str):
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            cursor = conn.execute(
                "SELECT d.id, d.ot, d.alias, d.setcode, d.type, d.atk, d.def, "
                "d.level, d.race, d.attribute, d.category "
                "FROM datas d"
            )
            for row in cursor:
                card_id = row[0]
                level = row[7]
                self._cards[card_id] = {
                    "code": card_id,
                    "alias": row[2],
                    "setcodes": self._parse_setcodes(row[3]),
                    "type": row[4],
                    "attack": row[5],
                    "defense": row[6],
                    "level": level & 0xFF,
                    "race": row[8],
                    "attribute": row[9],
                    "lscale": (level >> 24) & 0xFF,
                    "rscale": (level >> 16) & 0xFF,
                    "link_marker": row[6] if (row[4] & 0x4000000) else 0,
                }
            conn.close()
        except Exception as e:
            logger.error("Failed to load card database %s: %s", path, e)

    @staticmethod
    def _parse_setcodes(setcode: int) -> list[int]:
        codes = []
        for i in range(4):
            sc = (setcode >> (i * 16)) & 0xFFFF
            if sc:
                codes.append(sc)
        return codes

    def get_card(self, code: int) -> dict | None:
        return self._cards.get(code)

    def get_type(self, code: int) -> int:
        card = self._cards.get(code)
        return int(card["type"]) if card else 0


# --- Core Wrapper ---

class OcgCore:
    """Wrapper around ocgcore shared library."""

    def __init__(self, lib_path: str, db_paths: list[str], script_dir: str = ""):
        self._db = CardDatabase(db_paths)
        self._script_dir = Path(script_dir) if script_dir else None
        self._lib = self._load_library(lib_path)
        self._setup_functions()
        self._setcode_buffers: dict[int, ctypes.Array] = {}

        # Keep callback references alive (prevent GC)
        self._card_reader_cb = OCG_DataReaderFunc(self._card_reader)
        self._card_reader_done_cb = OCG_DataReaderDoneFunc(self._card_reader_done)
        self._script_reader_cb = OCG_ScriptReaderFunc(self._script_reader)
        self._log_handler_cb = OCG_LogHandlerFunc(self._log_handler)

    @staticmethod
    def _load_library(lib_path: str):
        path = Path(lib_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"ocgcore library not found: {lib_path}")
        if sys.platform == "win32":
            _validate_windows_library_architecture(path)
            if hasattr(__import__("os"), "add_dll_directory"):
                import os

                _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(path.parent)))
            return ctypes.CDLL(str(path))
        else:
            return ctypes.cdll.LoadLibrary(str(path))

    def _setup_functions(self):
        lib = self._lib

        lib.OCG_GetVersion.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
        lib.OCG_GetVersion.restype = None

        lib.OCG_CreateDuel.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(OCG_DuelOptions)]
        lib.OCG_CreateDuel.restype = ctypes.c_int

        lib.OCG_DestroyDuel.argtypes = [ctypes.c_void_p]
        lib.OCG_DestroyDuel.restype = None

        lib.OCG_DuelNewCard.argtypes = [ctypes.c_void_p, ctypes.POINTER(OCG_NewCardInfo)]
        lib.OCG_DuelNewCard.restype = None

        lib.OCG_StartDuel.argtypes = [ctypes.c_void_p]
        lib.OCG_StartDuel.restype = None

        lib.OCG_DuelProcess.argtypes = [ctypes.c_void_p]
        lib.OCG_DuelProcess.restype = ctypes.c_int

        lib.OCG_DuelGetMessage.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        lib.OCG_DuelGetMessage.restype = ctypes.c_void_p

        lib.OCG_DuelSetResponse.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
        lib.OCG_DuelSetResponse.restype = None

        lib.OCG_LoadScript.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_char_p]
        lib.OCG_LoadScript.restype = ctypes.c_int

        lib.OCG_DuelQueryCount.argtypes = [ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint32]
        lib.OCG_DuelQueryCount.restype = ctypes.c_uint32

        lib.OCG_DuelQuery.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(OCG_QueryInfo)]
        lib.OCG_DuelQuery.restype = ctypes.c_void_p

        lib.OCG_DuelQueryLocation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(OCG_QueryInfo)]
        lib.OCG_DuelQueryLocation.restype = ctypes.c_void_p

        lib.OCG_DuelQueryField.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        lib.OCG_DuelQueryField.restype = ctypes.c_void_p

    def card_type(self, code: int) -> int:
        """Card type bits, or 0 when the databases do not know the card."""
        return self._db.get_type(code)

    def get_version(self) -> tuple[int, int]:
        major = ctypes.c_int()
        minor = ctypes.c_int()
        self._lib.OCG_GetVersion(ctypes.byref(major), ctypes.byref(minor))
        return major.value, minor.value

    def create_duel(self, seed: int, flags: int = 0,
                    lp: int = 8000, draw_count: int = 1, start_count: int = 5) -> ctypes.c_void_p:
        """Create a new duel instance with given parameters."""
        options = OCG_DuelOptions()
        options.seed[0] = seed & 0xFFFFFFFFFFFFFFFF
        options.seed[1] = (seed >> 64) & 0xFFFFFFFFFFFFFFFF if seed > 0xFFFFFFFFFFFFFFFF else 0
        options.seed[2] = 0
        options.seed[3] = 0
        options.flags = flags
        options.team1 = OCG_Player(lp, start_count, draw_count)
        options.team2 = OCG_Player(lp, start_count, draw_count)
        options.cardReader = self._card_reader_cb
        options.payload1 = None
        options.scriptReader = self._script_reader_cb
        options.payload2 = None
        options.logHandler = self._log_handler_cb
        options.payload3 = None
        options.cardReaderDone = self._card_reader_done_cb
        options.payload4 = None
        options.enableUnsafeLibraries = 0

        duel = ctypes.c_void_p()
        status = self._lib.OCG_CreateDuel(ctypes.byref(duel), ctypes.byref(options))
        if status != OCG_DUEL_CREATION_SUCCESS:
            raise RuntimeError(f"OCG_CreateDuel failed with status {status}")
        logger.debug("Duel created (handle=%s)", duel.value)
        self._preload_global_scripts(duel)
        return duel

    def destroy_duel(self, duel: ctypes.c_void_p):
        self._lib.OCG_DestroyDuel(duel)

    def new_card(self, duel: ctypes.c_void_p, code: int, owner: int, player: int,
                 location: int, sequence: int, position: int):
        """Add a card to the duel (used for deck loading)."""
        info = OCG_NewCardInfo()
        info.team = owner
        info.duelist = 0
        info.code = code
        info.con = player
        info.loc = location
        info.seq = sequence
        info.pos = position
        self._lib.OCG_DuelNewCard(duel, ctypes.byref(info))

    def start_duel(self, duel: ctypes.c_void_p):
        self._lib.OCG_StartDuel(duel)

    def process(self, duel: ctypes.c_void_p) -> int:
        """Advance the duel. Returns OCG_DUEL_STATUS_*."""
        return self._lib.OCG_DuelProcess(duel)

    def get_message(self, duel: ctypes.c_void_p) -> bytes:
        """Get pending game message buffer."""
        length = ctypes.c_uint32()
        ptr = self._lib.OCG_DuelGetMessage(duel, ctypes.byref(length))
        if not ptr or length.value == 0:
            return b""
        return ctypes.string_at(ptr, length.value)

    def set_response(self, duel: ctypes.c_void_p, response: bytes):
        """Feed player response back to the engine."""
        buf = ctypes.create_string_buffer(response)
        self._lib.OCG_DuelSetResponse(duel, buf, len(response))

    def load_script(self, duel: ctypes.c_void_p, script_name: str, script_content: bytes) -> bool:
        """Load a Lua script into the duel."""
        name = script_name.encode("utf-8")
        result = self._lib.OCG_LoadScript(duel, script_content, len(script_content), name)
        return result == 1

    def query_count(self, duel: ctypes.c_void_p, team: int, location: int) -> int:
        return self._lib.OCG_DuelQueryCount(duel, team, location)

    def query(self, duel: ctypes.c_void_p, flags: int, controller: int,
              location: int, sequence: int, overlay_seq: int = 0) -> bytes:
        info = OCG_QueryInfo()
        info.flags = flags
        info.con = controller
        info.loc = location
        info.seq = sequence
        info.overlay_seq = overlay_seq
        length = ctypes.c_uint32()
        ptr = self._lib.OCG_DuelQuery(duel, ctypes.byref(length), ctypes.byref(info))
        if not ptr or length.value == 0:
            return b""
        return ctypes.string_at(ptr, length.value)

    def query_location(self, duel: ctypes.c_void_p, flags: int, controller: int,
                       location: int) -> bytes:
        """Query a whole location at once.

        Returns the core's query buffer: one chunk per field, a QUERY_END chunk
        per card, and a zero length chunk for each empty zone.
        """
        info = OCG_QueryInfo()
        info.flags = flags
        info.con = controller
        info.loc = location
        info.seq = 0
        info.overlay_seq = 0
        length = ctypes.c_uint32()
        ptr = self._lib.OCG_DuelQueryLocation(duel, ctypes.byref(length), ctypes.byref(info))
        if not ptr or length.value == 0:
            return b""
        return ctypes.string_at(ptr, length.value)

    def query_field(self, duel: ctypes.c_void_p) -> bytes:
        length = ctypes.c_uint32()
        ptr = self._lib.OCG_DuelQueryField(duel, ctypes.byref(length))
        if not ptr or length.value == 0:
            return b""
        return ctypes.string_at(ptr, length.value)

    # --- Callbacks ---

    def _card_reader(self, payload, code: int, data_ptr):
        """Called by ocgcore to read card data."""
        card = self._db.get_card(code)
        if not card:
            data_ptr.contents.code = code
            return

        data_ptr.contents.code = card["code"]
        data_ptr.contents.alias = card["alias"]
        data_ptr.contents.type = card["type"]
        data_ptr.contents.level = card["level"]
        data_ptr.contents.attribute = card["attribute"]
        data_ptr.contents.race = card["race"]
        data_ptr.contents.attack = card["attack"]
        data_ptr.contents.defense = card["defense"]
        data_ptr.contents.lscale = card["lscale"]
        data_ptr.contents.rscale = card["rscale"]
        data_ptr.contents.link_marker = card["link_marker"]

        setcodes = card["setcodes"] + [0]  # null-terminated
        arr = (ctypes.c_uint16 * len(setcodes))(*setcodes)
        self._setcode_buffers[code] = arr
        data_ptr.contents.setcodes = ctypes.cast(arr, ctypes.POINTER(ctypes.c_uint16))

    def _card_reader_done(self, payload, data_ptr):
        """Cleanup after card data read."""
        code = data_ptr.contents.code
        self._setcode_buffers.pop(code, None)

    def _script_reader(self, payload, duel, name: bytes) -> int:
        """Called by ocgcore to load Lua scripts."""
        script_name = name.decode("utf-8")
        script_path = self._resolve_script_path(script_name)
        if not script_path.exists():
            logger.debug("Script not found: %s", script_name)
            return 0
        content = script_path.read_bytes()
        return int(self.load_script(duel, script_name, content))

    def _resolve_script_path(self, script_name: str) -> Path:
        if not self._script_dir:
            return Path()
        script_path = self._script_dir / script_name
        if script_path.exists():
            return script_path
        return self._script_dir / "official" / script_name

    def _preload_global_scripts(self, duel: ctypes.c_void_p) -> None:
        """Load EDOPro global scripts required before card scripts run."""
        for script_name in ("constant.lua", "utility.lua"):
            script_path = self._resolve_script_path(script_name)
            if not script_path.exists():
                logger.debug("Global script not found: %s", script_name)
                continue
            self.load_script(duel, script_name, script_path.read_bytes())

    def _log_handler(self, payload, message: bytes, msg_type: int):
        """Called by ocgcore for log messages."""
        if message:
            logger.debug("[ocgcore] %s", message.decode("utf-8", errors="replace"))


def _validate_windows_library_architecture(path: Path) -> None:
    machine = _read_pe_machine(path)
    if machine is None:
        return

    process_bits = struct.calcsize("P") * 8
    machine_bits = {
        0x014C: 32,
        0x8664: 64,
        0xAA64: 64,
    }.get(machine)
    if machine_bits and machine_bits != process_bits:
        raise OSError(
            f"ocgcore architecture mismatch: {path.name} is {machine_bits}-bit "
            f"but Python is {process_bits}-bit. Use a matching ocgcore build "
            "or run the client with matching Python architecture."
        )


def _read_pe_machine(path: Path) -> int | None:
    try:
        with path.open("rb") as fp:
            header = fp.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return None
            pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
            fp.seek(pe_offset)
            pe_header = fp.read(6)
            if len(pe_header) < 6 or pe_header[:4] != b"PE\0\0":
                return None
            return struct.unpack_from("<H", pe_header, 4)[0]
    except OSError:
        return None
