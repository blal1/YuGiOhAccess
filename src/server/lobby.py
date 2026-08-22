"""TCP lobby server — accepts EDOPro client connections and manages rooms."""

import asyncio
import logging
import os
import struct
import time
import ctypes

from server.protocol import (
    ClientPacket, ServerPacket, RoomState,
    encode_packet, read_packet, encode_string_utf16, decode_string_utf16,
)
from core import variables
from core.i18n import _
from game.edo import structs
from game.edo.structs_utils import u16_to_string

logger = logging.getLogger(__name__)


class PlayerConnection:
    """Represents a single TCP client connection."""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.name: str = ""
        self.version: int = 0
        self.room: "Room | None" = None
        self.slot: int = -1  # 0 or 1 for players, -1 for observers
        self.ready: bool = False
        self.deck_main: list[int] = []
        self.deck_extra: list[int] = []
        self.deck_side: list[int] = []
        self._closed = False

    @property
    def address(self) -> str:
        peername = self.writer.get_extra_info("peername")
        return f"{peername[0]}:{peername[1]}" if peername else "unknown"

    async def send(self, packet_id: int, data: bytes = b""):
        if self._closed:
            return
        try:
            self.writer.write(encode_packet(packet_id, data))
            await self.writer.drain()
        except (ConnectionError, OSError):
            self._closed = True

    def close(self):
        if not self._closed:
            self._closed = True
            self.writer.close()

    @property
    def is_closed(self) -> bool:
        return self._closed


class Room:
    """A game room that holds two player slots and observers."""

    def __init__(self, room_id: int, host_info: dict):
        self.room_id = room_id
        self.host_info = host_info
        self.password: str = host_info.get("password", "")
        self.players: list[PlayerConnection | None] = [None, None]
        self.observers: list[PlayerConnection] = []
        self.state = RoomState.WAITING
        self.created_at = time.time()
        self.duel = None  # Set when duel starts
        self.start_requested = False

    @property
    def player_count(self) -> int:
        return sum(1 for p in self.players if p is not None)

    def add_player(self, conn: PlayerConnection) -> int:
        """Add player to first available slot. Returns slot index or -1."""
        for i in range(2):
            if self.players[i] is None:
                self.players[i] = conn
                conn.slot = i
                conn.room = self
                return i
        return -1

    def remove_player(self, conn: PlayerConnection):
        if conn.slot >= 0 and conn.slot < 2 and self.players[conn.slot] is conn:
            self.players[conn.slot] = None
        elif conn in self.observers:
            self.observers.remove(conn)
        conn.room = None
        conn.slot = -1

    def add_observer(self, conn: PlayerConnection):
        self.observers.append(conn)
        conn.room = self
        conn.slot = -1

    async def broadcast(self, packet_id: int, data: bytes = b"", exclude: PlayerConnection | None = None):
        """Send packet to all players and observers."""
        targets = [p for p in self.players if p and p is not exclude]
        targets += [o for o in self.observers if o is not exclude]
        for conn in targets:
            await conn.send(packet_id, data)

    async def broadcast_players(self, packet_id: int, data: bytes = b""):
        """Send packet to player slots only."""
        for p in self.players:
            if p:
                await p.send(packet_id, data)

    def to_json(self) -> dict:
        """Room info as JSON (compatible with ProjectIgnis room listing)."""
        users = []
        for i, p in enumerate(self.players):
            if p:
                users.append({"name": p.name, "pos": i})
        for o in self.observers:
            users.append({"name": o.name, "pos": 7})
        return {
            "roomid": self.room_id,
            "roomname": self.host_info.get("name", ""),
            "roomnotes": self.host_info.get("notes", ""),
            "roommode": self.host_info.get("mode", 0),
            "banlist_hash": self.host_info.get("banlist_hash", self.host_info.get("lflist", 0)),
            "lflist": self.host_info.get("lflist", self.host_info.get("banlist_hash", 0)),
            "needpass": bool(self.password),
            "users": users,
            "istart": "dueling" if self.state == RoomState.DUELING else "waiting",
            "team1": self.host_info.get("t0_count", 1),
            "team2": self.host_info.get("t1_count", 1),
            "best_of": self.host_info.get("best_of", 1),
            "time_limit": self.host_info.get("time_limit", 180),
            "start_lp": self.host_info.get("start_lp", 8000),
            "start_hand": self.host_info.get("start_hand", 5),
            "draw_count": self.host_info.get("draw_count", 1),
            "host_info": self.host_info,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.created_at)),
        }


class LobbyServer:
    """Main TCP server handling EDOPro protocol connections."""

    def __init__(self, duel_engine=None):
        self.rooms: dict[str, Room] = {}
        self.connections: list[PlayerConnection] = []
        self.duel_engine = duel_engine
        self._server: asyncio.Server | None = None

    async def start(self, host: str = "0.0.0.0", port: int = 7933):
        self._server = await asyncio.start_server(self._handle_connection, host, port)
        logger.info("Lobby server listening on %s:%d", host, port)

    async def stop(self):
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for conn in self.connections:
            conn.close()

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        conn = PlayerConnection(reader, writer)
        self.connections.append(conn)
        logger.debug("New connection from %s", conn.address)

        try:
            while not conn.is_closed:
                try:
                    result = await read_packet(reader)
                except (asyncio.IncompleteReadError, ConnectionError):
                    break
                if result is None:
                    break
                packet_id, payload = result
                await self._dispatch_packet(conn, packet_id, payload)
        except Exception as e:
            logger.error("Connection error from %s: %s", conn.address, e)
        finally:
            await self._handle_disconnect(conn)
            self.connections.remove(conn)
            conn.close()

    async def _dispatch_packet(self, conn: PlayerConnection, packet_id: int, payload: bytes):
        handlers = {
            ClientPacket.PLAYER_INFO: self._handle_player_info,
            ClientPacket.CREATE_GAME: self._handle_create_game,
            ClientPacket.JOIN_GAME: self._handle_join_game,
            ClientPacket.LEAVE_GAME: self._handle_leave_game,
            ClientPacket.READY: self._handle_ready,
            ClientPacket.NOT_READY: self._handle_not_ready,
            ClientPacket.TRY_START: self._handle_try_start,
            ClientPacket.UPDATE_DECK: self._handle_update_deck,
            ClientPacket.CHAT: self._handle_chat,
            ClientPacket.RESPONSE: self._handle_response,
            ClientPacket.RPS_CHOICE: self._handle_rps_choice,
            ClientPacket.TURN_CHOICE: self._handle_turn_choice,
            ClientPacket.SURRENDER: self._handle_surrender,
            ClientPacket.REMATCH: self._handle_rematch,
            ClientPacket.TO_OBSERVER: self._handle_to_observer,
            ClientPacket.TO_DUELIST: self._handle_to_duelist,
        }
        handler = handlers.get(packet_id)
        if handler:
            await handler(conn, payload)
        else:
            logger.debug("Unhandled packet 0x%02X from %s", packet_id, conn.name or conn.address)

    async def _handle_player_info(self, conn: PlayerConnection, payload: bytes):
        conn.name = decode_string_utf16(payload[:40])
        logger.debug("Player identified: %s", conn.name)

    @staticmethod
    def _is_bot_connection(conn: PlayerConnection) -> bool:
        return conn.name.strip().lower().startswith("windbot")

    @staticmethod
    def _should_auto_ready(conn: PlayerConnection) -> bool:
        if conn.slot <= 0:
            return False
        return not conn.name.strip() or LobbyServer._is_bot_connection(conn)

    async def _set_player_ready(self, conn: PlayerConnection, ready: bool):
        if not conn.room or conn.slot < 0:
            return
        conn.ready = ready
        change_type = 0x09 if ready else 0x0A
        change_data = struct.pack("B", (conn.slot << 4) | change_type)
        await conn.room.broadcast(ServerPacket.PLAYER_CHANGE, change_data)

    async def _auto_ready_local_bots(self, room: Room):
        for player in room.players:
            if player and not player.ready and self._should_auto_ready(player):
                await self._set_player_ready(player, True)

    async def _handle_create_game(self, conn: PlayerConnection, payload: bytes):
        host_info = self._parse_host_info(payload)
        room_id = self._generate_room_id()
        room = Room(room_id, host_info)
        self.rooms[room_id] = room

        slot = room.add_player(conn)
        logger.info("Room %s created by %s", room_id, conn.name)

        await conn.send(ServerPacket.CREATE_GAME, self._encode_room_created(room))
        await conn.send(ServerPacket.JOIN_GAME, self._encode_join_game(host_info))
        await conn.send(ServerPacket.TYPE_CHANGE, struct.pack("B", 0x10 | slot))

    async def _handle_join_game(self, conn: PlayerConnection, payload: bytes):
        if len(payload) < ctypes.sizeof(structs.JoinGame):
            await self._send_error(conn, 2, 0)
            return

        room = None
        room_pass = ""
        for room_id, candidate_pass in self._join_game_candidates(payload):
            room_pass = candidate_pass
            room = self.rooms.get(room_id)
            if not room and candidate_pass:
                # Try matching by password
                for r in self.rooms.values():
                    if (r.password and r.password == candidate_pass) or str(r.room_id) == candidate_pass:
                        room = r
                        break
            if room:
                break

        if not room:
            await self._send_error(conn, 2, 0)
            return

        if room.password and room_pass != room.password and room_pass != str(room.room_id):
            await self._send_error(conn, 1, 0)
            return

        slot = room.add_player(conn)
        if slot < 0:
            room.add_observer(conn)

        await conn.send(ServerPacket.JOIN_GAME, self._encode_join_game(room.host_info))
        await conn.send(ServerPacket.TYPE_CHANGE, struct.pack("B", conn.slot if conn.slot >= 0 else 7))

        # Notify existing players
        player_enter_data = encode_string_utf16(conn.name, 20) + struct.pack("B", conn.slot if conn.slot >= 0 else 7)
        await room.broadcast(ServerPacket.PLAYER_ENTER, player_enter_data, exclude=conn)

        # Send existing players to new connection
        for i, p in enumerate(room.players):
            if p and p is not conn:
                data = encode_string_utf16(p.name, 20) + struct.pack("B", i)
                await conn.send(ServerPacket.PLAYER_ENTER, data)

        if conn.slot >= 0 and self._should_auto_ready(conn):
            await self._set_player_ready(conn, True)

    @staticmethod
    def _join_game_candidates(payload: bytes):
        candidates = []
        if len(payload) >= ctypes.sizeof(structs.JoinGame):
            join = structs.JoinGame.from_buffer_copy(payload[:ctypes.sizeof(structs.JoinGame)])
            candidates.append((int(join.id), u16_to_string(join.password)))
        # WindBot's JoinGame packet contains two padding bytes between version2
        # and room id, then writes the room id again as the password/host info.
        if len(payload) >= 48:
            room_id = struct.unpack_from("<I", payload, 4)[0]
            room_pass = decode_string_utf16(payload[8:48])
            candidate = (room_id, room_pass)
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    async def _handle_to_observer(self, conn: PlayerConnection, payload: bytes):
        if not conn.room:
            return
        room = conn.room
        if conn.slot >= 0 and conn.slot < len(room.players) and room.players[conn.slot] is conn:
            room.players[conn.slot] = None
        if conn not in room.observers:
            room.add_observer(conn)
        await conn.send(ServerPacket.TYPE_CHANGE, struct.pack("B", 7))
        await room.broadcast(ServerPacket.PLAYER_CHANGE, struct.pack("B", 0x78), exclude=conn)

    async def _handle_to_duelist(self, conn: PlayerConnection, payload: bytes):
        if not conn.room:
            return
        room = conn.room
        if conn in room.observers:
            room.observers.remove(conn)
        slot = room.add_player(conn)
        if slot < 0:
            room.add_observer(conn)
            await conn.send(ServerPacket.TYPE_CHANGE, struct.pack("B", 7))
            return
        await conn.send(ServerPacket.TYPE_CHANGE, struct.pack("B", slot))

    async def _handle_leave_game(self, conn: PlayerConnection, payload: bytes):
        await self._handle_disconnect(conn)

    async def _handle_ready(self, conn: PlayerConnection, payload: bytes):
        await self._set_player_ready(conn, True)

    async def _handle_not_ready(self, conn: PlayerConnection, payload: bytes):
        await self._set_player_ready(conn, False)

    async def _handle_try_start(self, conn: PlayerConnection, payload: bytes):
        if not conn.room or conn.slot != 0:
            return
        room = conn.room
        room.start_requested = True
        await self._try_start_room(room, report_waiting=True)

    async def _try_start_room(self, room: Room, report_waiting: bool = False):
        if room.state != RoomState.WAITING:
            return False
        await self._auto_ready_local_bots(room)
        if not all(p and p.ready for p in room.players):
            if report_waiting:
                await self._send_system_message(room, _("Cannot start yet: waiting for every player to be ready."))
            return False
        if not all(p.deck_main for p in room.players if p):
            if report_waiting:
                await self._send_system_message(room, _("Cannot start yet: waiting for every player deck to be loaded."))
            return False
        if self.duel_engine is None:
            await self._send_engine_unavailable(room)
            return False
        await self._start_duel(room)
        return True

    async def _handle_update_deck(self, conn: PlayerConnection, payload: bytes):
        if not conn.room:
            return
        offset = 0
        main_count = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        side_count = struct.unpack_from("<I", payload, offset)[0]
        offset += 4

        conn.deck_main = []
        conn.deck_extra = []
        for _ in range(main_count):
            card_id = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            # Cards with type including 0x4000 (extra deck types) go to extra
            conn.deck_main.append(card_id)

        conn.deck_side = []
        for _ in range(side_count):
            card_id = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            conn.deck_side.append(card_id)
        if self._should_auto_ready(conn):
            await self._set_player_ready(conn, True)
        if conn.room.start_requested:
            await self._try_start_room(conn.room)

    async def _handle_chat(self, conn: PlayerConnection, payload: bytes):
        if not conn.room:
            return
        msg = decode_string_utf16(payload)
        chat_type = conn.slot if conn.slot >= 0 else 8
        chat_data = struct.pack("BB", chat_type, 0)
        chat_data += encode_string_utf16(conn.name, 20)
        chat_data += encode_string_utf16(msg, 256)
        await conn.room.broadcast(ServerPacket.CHAT_2, chat_data, exclude=conn)

    async def _handle_response(self, conn: PlayerConnection, payload: bytes):
        if not conn.room or not conn.room.duel:
            return
        await conn.room.duel.handle_response(conn, payload)

    async def _handle_rps_choice(self, conn: PlayerConnection, payload: bytes):
        if not conn.room or not conn.room.duel:
            return
        await conn.room.duel.handle_rps_choice(conn, payload)

    async def _handle_turn_choice(self, conn: PlayerConnection, payload: bytes):
        if not conn.room or not conn.room.duel:
            return
        await conn.room.duel.handle_turn_choice(conn, payload)

    async def _handle_surrender(self, conn: PlayerConnection, payload: bytes):
        if not conn.room or not conn.room.duel:
            return
        await conn.room.duel.handle_surrender(conn)

    async def _handle_rematch(self, conn: PlayerConnection, payload: bytes):
        if not conn.room:
            return
        # Simple rematch: reset room state
        conn.room.state = RoomState.WAITING
        conn.ready = False

    async def _handle_disconnect(self, conn: PlayerConnection):
        if conn.room:
            room = conn.room
            old_slot = conn.slot
            room.remove_player(conn)
            if room.player_count == 0 and not room.observers:
                self.rooms.pop(room.room_id, None)
                logger.info("Room %s destroyed (empty)", room.room_id)
            else:
                leave_data = struct.pack("B", ((old_slot if old_slot >= 0 else 7) << 4) | 0x0B)
                await room.broadcast(ServerPacket.PLAYER_CHANGE, leave_data)

    async def _start_duel(self, room: Room):
        """Initiate the RPS/duel sequence."""
        from server.duel import DuelInstance

        if self.duel_engine is None:
            await self._send_engine_unavailable(room)
            return
        room.state = RoomState.RPS
        room.duel = DuelInstance(room, self.duel_engine)

        await room.broadcast_players(ServerPacket.DUEL_START, b"")
        await room.duel.start_rps()

    async def _send_error(self, conn: PlayerConnection, error_type: int, code: int):
        data = struct.pack("<BI", error_type, code)
        await conn.send(ServerPacket.ERROR_MSG, data)

    async def _send_engine_unavailable(self, room: Room):
        message = _("Local EDOPro engine is not available. Build or configure ocgcore first.")
        await self._send_system_message(room, message, send_error=True)

    async def _send_system_message(self, room: Room, message: str, send_error: bool = False):
        data = struct.pack("BB", 3, 0)
        data += encode_string_utf16("System", 20)
        data += encode_string_utf16(message, 256)
        await room.broadcast(ServerPacket.CHAT_2, data)
        if send_error:
            for player in room.players:
                if player:
                    await self._send_error(player, 4, 0)

    def _generate_room_id(self) -> int:
        while True:
            room_id = struct.unpack("<I", os.urandom(4))[0] or 1
            if room_id not in self.rooms:
                return room_id

    @staticmethod
    def _parse_host_info(payload: bytes) -> dict:
        """Parse CREATE_GAME packet into host info dict using client struct layout."""
        if len(payload) < ctypes.sizeof(structs.CreateGame):
            return {}
        packet = structs.CreateGame.from_buffer_copy(payload[:ctypes.sizeof(structs.CreateGame)])
        host = packet.host_info
        return {
            "lflist": int(host.banlist_hash),
            "banlist_hash": int(host.banlist_hash),
            "allowed": int(host.allowed),
            "mode": int(host.mode),
            "duel_rule": int(host.duel_rule),
            "rule": int(host.duel_rule),
            "no_check_deck": int(host.dont_check_deck_content),
            "no_shuffle_deck": int(host.dont_shuffle_deck),
            "start_lp": int(host.starting_lp),
            "start_hand": int(host.starting_draw_count),
            "draw_count": int(host.draw_count_per_turn),
            "time_limit": int(host.time_limit_in_seconds),
            "duel_flags": (int(host.duel_flags_high) << 32) | int(host.duel_flags_low),
            "handshake": int(host.handshake),
            "version": bytes(host.version),
            "t0_count": max(1, int(host.t0_count)),
            "t1_count": max(1, int(host.t1_count)),
            "best_of": max(1, int(host.best_of)),
            "forbidden_types": int(host.forbidden_types),
            "extra_rules": int(host.extra_rules),
            "name": u16_to_string(packet.name),
            "password": u16_to_string(packet.password),
            "notes": bytes(packet.notes).split(b"\x00", 1)[0].decode("utf-8", errors="replace"),
        }

    @staticmethod
    def _encode_room_created(room: Room) -> bytes:
        return struct.pack("<I", room.room_id)

    @staticmethod
    def _encode_join_game(host_info: dict) -> bytes:
        duel_flags = host_info.get("duel_flags", 0)
        version = host_info.get("version", bytes(variables.edo_client_version))
        if len(version) < 4:
            version = bytes(variables.edo_client_version)
        handshake = int(host_info.get("handshake") or 4043399681)
        return struct.pack(
            "<IBBBBB3xIBBHII4siiiIii",
            int(host_info.get("banlist_hash", host_info.get("lflist", 0))),
            int(host_info.get("allowed", 0)),
            int(host_info.get("mode", 0)),
            int(host_info.get("duel_rule", host_info.get("rule", 5))),
            int(host_info.get("no_check_deck", 0)),
            int(host_info.get("no_shuffle_deck", 0)),
            int(host_info.get("start_lp", 8000)),
            int(host_info.get("start_hand", 5)),
            int(host_info.get("draw_count", 1)),
            int(host_info.get("time_limit", 180)),
            (int(duel_flags) >> 32) & 0xFFFFFFFF,
            handshake,
            version[:4],
            int(host_info.get("t0_count", 1)),
            int(host_info.get("t1_count", 1)),
            int(host_info.get("best_of", 1)),
            int(duel_flags) & 0xFFFFFFFF,
            int(host_info.get("forbidden_types", 0)),
            int(host_info.get("extra_rules", 0)),
        )
