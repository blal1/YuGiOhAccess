"""EDOPro binary protocol constants and packet I/O helpers."""

import struct
import enum


class ClientPacket(enum.IntEnum):
    RESPONSE = 0x01
    UPDATE_DECK = 0x02
    RPS_CHOICE = 0x03
    TURN_CHOICE = 0x04
    PLAYER_INFO = 0x10
    CREATE_GAME = 0x11
    JOIN_GAME = 0x12
    LEAVE_GAME = 0x13
    SURRENDER = 0x14
    TIME_CONFIRM = 0x15
    CHAT = 0x16
    TO_DUELIST = 0x20
    TO_OBSERVER = 0x21
    READY = 0x22
    NOT_READY = 0x23
    TRY_KICK = 0x24
    TRY_START = 0x25
    REMATCH = 0xF0


class ServerPacket(enum.IntEnum):
    GAME_MSG = 0x01
    ERROR_MSG = 0x02
    CHOOSE_RPS = 0x03
    CHOOSE_ORDER = 0x04
    RPS_RESULT = 0x05
    ORDER_RESULT = 0x06
    CHANGE_SIDE = 0x07
    WAITING_SIDE = 0x08
    CREATE_GAME = 0x11
    JOIN_GAME = 0x12
    TYPE_CHANGE = 0x13
    LEAVE_GAME = 0x14
    DUEL_START = 0x15
    DUEL_END = 0x16
    REPLAY = 0x17
    TIME_LIMIT = 0x18
    PLAYER_ENTER = 0x20
    PLAYER_CHANGE = 0x21
    WATCH_CHANGE = 0x22
    NEW_REPLAY = 0x30
    CATCHUP = 0xF0
    REMATCH = 0xF1
    REMATCH_WAIT = 0xF2
    CHAT_2 = 0xF3


class RoomState(enum.IntEnum):
    WAITING = 0
    RPS = 1
    CHOOSING_ORDER = 2
    DUELING = 3
    SIDE_DECKING = 4
    ENDED = 5


HEADER_SIZE = 3  # 2-byte length + 1-byte packet ID


def encode_packet(packet_id: int, data: bytes = b"") -> bytes:
    """Encode a packet with length header for sending over TCP."""
    length = len(data) + 1  # +1 for packet ID byte
    return struct.pack("<H", length) + struct.pack("B", packet_id) + data


async def read_packet(reader) -> tuple[int, bytes] | None:
    """Read one packet from asyncio StreamReader. Returns (packet_id, payload) or None on EOF."""
    header = await reader.readexactly(2)
    if not header:
        return None
    length = struct.unpack("<H", header)[0]
    if length < 1:
        return None
    body = await reader.readexactly(length)
    packet_id = body[0]
    payload = body[1:]
    return packet_id, payload


def encode_string_utf16(s: str, max_length: int = 20) -> bytes:
    """Encode string as UTF-16LE with fixed buffer size (null-padded)."""
    encoded = s.encode("utf-16-le")
    buf = bytearray(max_length * 2)
    buf[:len(encoded)] = encoded[:max_length * 2 - 2]
    return bytes(buf)


def decode_string_utf16(data: bytes) -> str:
    """Decode UTF-16LE string, stripping null terminators."""
    return data.decode("utf-16-le").rstrip("\x00")
