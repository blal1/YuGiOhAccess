"""TCP lobby server — accepts EDOPro client connections and manages rooms."""

import asyncio
import logging
import os
import struct
import time
import ctypes
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    # Imported for typing only: server.duel imports this module at runtime.
    from server.duel import DuelInstance

from server import deck_check
from server.protocol import (
    ClientPacket, ServerPacket, RoomState,
    encode_packet, read_packet, encode_string_utf16, decode_string_utf16,
)
from core import variables
from core.i18n import _
from game.edo import default_values, structs
from game.edo.structs_utils import u16_to_string

logger = logging.getLogger(__name__)

# Monster types that live in the extra deck (fusion, synchro, xyz, link).
EXTRA_DECK_TYPES = 0x40 | 0x2000 | 0x800000 | 0x4000000


def _client_version(raw) -> structs.ClientVersion:
    """A ClientVersion from whatever the create packet carried, or ours."""
    if isinstance(raw, (bytes, bytearray)) and len(raw) >= ctypes.sizeof(structs.ClientVersion):
        return structs.ClientVersion.from_buffer_copy(bytes(raw))
    return variables.edo_client_version


def _deck_limits(raw) -> structs.DeckLimits:
    """The deck size limits the room was created with, or the standard ones.

    A client that leaves this part of the create packet alone sends zeroes,
    and a room whose main deck may hold between zero and zero cards refuses
    every deck ever built. Zeroed limits mean "unspecified", not "nothing
    allowed".
    """
    if isinstance(raw, (bytes, bytearray)) and len(raw) >= ctypes.sizeof(structs.DeckLimits):
        limits = structs.DeckLimits.from_buffer_copy(bytes(raw))
        if limits.main.max or limits.extra.max or limits.side.max:
            return limits
    return default_values.DECK_LIMITS


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
        # Why this player's deck was refused, if it was.
        self.deck_error = None
        # Whether this player has said yes to a rematch.
        self.wants_rematch = False
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

    def __init__(self, room_id: int, host_info: dict, lobby: "LobbyServer | None" = None):
        self.room_id = room_id
        self.host_info = host_info
        # The server this room belongs to. A duel in progress needs a way back
        # to it to start the next game of a match.
        self.lobby = lobby
        self.password: str = host_info.get("password", "")
        self.players: list[PlayerConnection | None] = [None, None]
        self.observers: list[PlayerConnection] = []
        self.state = RoomState.WAITING
        self.created_at = time.time()
        self.duel: "DuelInstance | None" = None  # Set when a duel starts
        self.start_requested = False
        # Match play. Games won per room slot, and who still owes us a deck
        # between games. A best-of-three was previously unplayable here: the
        # first game ended and nothing ever sent CHANGE_SIDE, so both clients
        # sat waiting for a side deck prompt that never came.
        self.match_wins = [0, 0]
        self.games_played = 0
        self.awaiting_side_deck: set[int] = set()

    @property
    def best_of(self) -> int:
        return max(1, int(self.host_info.get("best_of", 1) or 1))

    @property
    def is_match(self) -> bool:
        return self.best_of > 1

    def wins_needed(self) -> int:
        return (self.best_of // 2) + 1

    def match_is_decided(self) -> bool:
        needed = self.wins_needed()
        if max(self.match_wins) >= needed:
            return True
        # Nobody can still reach the target, so there is nothing left to play.
        return self.games_played >= self.best_of

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
        # Keyed by room id, which is the integer _generate_room_id makes.
        self.rooms: dict[int, Room] = {}
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
        handlers: dict[int, Callable[[PlayerConnection, bytes], Awaitable[None]]] = {
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
            ClientPacket.TIME_CONFIRM: self._handle_time_confirm,
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
        room = Room(room_id, host_info, lobby=self)
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

        # A room with a duel already running has no seat to offer, whatever
        # its slots say: joining one means watching it.
        duel_in_progress = room.state not in (RoomState.WAITING, RoomState.ENDED)
        slot = -1 if duel_in_progress else room.add_player(conn)
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

        await self._catch_up_spectator(conn, room)

    async def _catch_up_spectator(self, conn: PlayerConnection, room: Room):
        """Replay a duel in progress to somebody who has just started watching."""
        if conn.slot >= 0 or room.duel is None:
            return
        if room.state not in (RoomState.DUELING, RoomState.RPS, RoomState.CHOOSING_ORDER):
            return
        await room.broadcast(
            ServerPacket.WATCH_CHANGE, struct.pack("<H", len(room.observers))
        )
        await room.duel.catch_up(conn)

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
        await self._catch_up_spectator(conn, room)

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

    async def _handle_time_confirm(self, conn: PlayerConnection, payload: bytes):
        """The client acknowledging its clock. Nothing to do but not complain.

        EDOPro clients answer every TIME_LIMIT with one of these; without a
        handler each one was logged as an unhandled packet.
        """
        logger.debug("%s confirmed its clock", conn.name or conn.address)

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
        # Checked again here rather than trusting the flag set when the deck
        # arrived: this is the last moment before the core is handed a deck it
        # may not be able to play.
        for player in room.players:
            if not player:
                continue
            player.deck_error = self._check_deck(room, player)
            if player.deck_error is None:
                continue
            logger.info(
                "Not starting room %s: %s's deck is illegal (%s)",
                room.room_id, player.name, deck_check.describe(player.deck_error),
            )
            await player.send(ServerPacket.ERROR_MSG, player.deck_error.to_bytes())
            if report_waiting:
                await self._send_system_message(
                    room,
                    _("Cannot start yet: {player} has a deck this room does not allow.").format(
                        player=player.name or _("a player")
                    ),
                )
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
        for _unused in range(main_count):
            card_id = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            # The client sends main and extra as one list; only the card type
            # says which is which. Leaving fusion, synchro, xyz and link
            # monsters in the main deck builds a deck ocgcore will not play.
            if self._is_extra_deck_card(card_id):
                conn.deck_extra.append(card_id)
            else:
                conn.deck_main.append(card_id)

        conn.deck_side = []
        for _unused in range(side_count):
            card_id = struct.unpack_from("<I", payload, offset)[0]
            offset += 4
            conn.deck_side.append(card_id)
        logger.debug(
            "Deck from %s: %d main, %d extra, %d side",
            conn.name, len(conn.deck_main), len(conn.deck_extra), len(conn.deck_side),
        )
        conn.deck_error = self._check_deck(conn.room, conn)
        if conn.deck_error is not None:
            logger.info(
                "Refusing %s's deck: %s",
                conn.name, deck_check.describe(conn.deck_error),
            )
            await conn.send(ServerPacket.ERROR_MSG, conn.deck_error.to_bytes())

        if conn.room.state == RoomState.SIDE_DECKING:
            if conn.deck_error is not None:
                # Keep asking: the game cannot start on a deck the core would
                # refuse, and the player is sitting in the side deck screen.
                await conn.send(ServerPacket.CHANGE_SIDE, b"")
                return
            await self._handle_side_deck_submitted(conn)
            return
        if conn.deck_error is not None:
            return
        if self._should_auto_ready(conn):
            await self._set_player_ready(conn, True)
        if conn.room.start_requested:
            await self._try_start_room(conn.room)

    async def _handle_side_deck_submitted(self, conn: PlayerConnection):
        """One player has finished siding. Start the next game once both have."""
        room = conn.room
        if room is None:
            # The player left between sending the deck and this running.
            logger.debug("Side deck arrived from %s, who is no longer in a room", conn.name)
            return
        room.awaiting_side_deck.discard(conn.slot)
        logger.info(
            "Room %s: %s finished side decking, still waiting for %s",
            room.room_id, conn.name, sorted(room.awaiting_side_deck) or "nobody",
        )
        if room.awaiting_side_deck:
            await conn.send(ServerPacket.WAITING_SIDE, b"")
            return
        await self._start_duel(room)

    async def _complete_side_decking_for_bots(self, room: Room):
        """A bot keeps the deck it already has.

        WindBot has no side deck step. Waiting for one from it would stop a
        match against a bot dead between games, which is the only kind of
        match this server is normally asked to run.
        """
        for slot in sorted(room.awaiting_side_deck):
            player = room.players[slot]
            if player and self._is_bot_connection(player):
                logger.info("Room %s: %s does not side deck; keeping its deck", room.room_id, player.name)
                room.awaiting_side_deck.discard(slot)
        if not room.awaiting_side_deck and room.state == RoomState.SIDE_DECKING:
            await self._start_duel(room)

    def _check_deck(self, room: Room, conn: PlayerConnection):
        """Whether this player's deck is legal for this room.

        The room can turn the content checks off, which is what
        ``dont_check_deck_content`` means, and a room with no banlist is only
        held to the standard three copies.
        """
        if int(room.host_info.get("no_check_deck", 0)):
            return None
        limits = _deck_limits(room.host_info.get("limits"))
        return deck_check.check_deck(
            conn.deck_main, conn.deck_extra, conn.deck_side,
            limits=limits,
            banlist=self._room_banlist(room),
            known_card=self._known_card,
        )

    def _room_banlist(self, room: Room):
        """The banlist this room was created with, if we can find it."""
        banlist_hash = int(room.host_info.get("banlist_hash", room.host_info.get("lflist", 0)) or 0)
        if not banlist_hash:
            return None
        try:
            from game.edo import banlists

            return banlists.BanlistManager().get_banlist_by_hash(banlist_hash)
        except Exception:
            logger.debug("No banlist available for hash %s", banlist_hash, exc_info=True)
            return None

    def _known_card(self, card_id: int) -> bool:
        """Whether the engine's databases have heard of this card.

        With no engine to ask, every card counts as known: refusing a deck for
        a card we merely cannot look up would make the server unusable rather
        than strict.
        """
        card_type = getattr(self.duel_engine, "card_type", None)
        if card_type is None:
            return True
        try:
            return bool(card_type(card_id))
        except Exception:
            logger.debug("Could not look up card %s", card_id, exc_info=True)
            return True

    def _is_extra_deck_card(self, card_id: int) -> bool:
        """Ask the engine's card database, and keep the card in the main deck
        when there is no database to ask: a deck that loads in the wrong pile
        still beats a deck that fails to load at all."""
        card_type = getattr(self.duel_engine, "card_type", None)
        if card_type is None:
            return False
        try:
            return bool(card_type(card_id) & EXTRA_DECK_TYPES)
        except Exception:
            logger.exception("Could not read the type of card %s", card_id)
            return False

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
        """One player answering the rematch question.

        This used to drop the room back to waiting on the first answer,
        whatever it was, without telling anyone: the player who said yes was
        left on a "waiting for opponent" screen forever, and the one who said
        no was silently put back in the room.
        """
        room = conn.room
        if not room or conn.slot < 0:
            return
        wants_rematch = bool(payload[0]) if payload else True
        conn.wants_rematch = wants_rematch
        logger.info(
            "Room %s: %s %s a rematch",
            room.room_id, conn.name, "wants" if wants_rematch else "declines",
        )

        if not wants_rematch:
            # Nothing more to wait for: tell the other seat it is over.
            for player in room.players:
                if player and player is not conn:
                    await player.send(ServerPacket.REMATCH_WAIT, b"")
                    await self._send_system_message(
                        room, _("Your opponent does not want a rematch.")
                    )
            self._reset_for_a_new_duel(room)
            return

        others = [p for p in room.players if p and p is not conn]
        if not all(getattr(player, "wants_rematch", False) for player in others):
            await conn.send(ServerPacket.REMATCH_WAIT, b"")
            return

        logger.info("Room %s: both players want a rematch", room.room_id)
        self._reset_for_a_new_duel(room)
        await self._try_start_room(room)

    @staticmethod
    def _reset_for_a_new_duel(room: Room):
        """Put the room back the way it was before the first duel."""
        room.state = RoomState.WAITING
        room.duel = None
        room.start_requested = False
        room.match_wins = [0, 0]
        room.games_played = 0
        room.awaiting_side_deck = set()
        for player in room.players:
            if player:
                player.ready = False
                player.wants_rematch = False

    async def offer_rematch(self, room: Room):
        """Ask both players whether they want to play again.

        Sent when a duel, or a whole match, is over. Nothing ever asked
        before, so the client's rematch screen could not appear.
        """
        for player in room.players:
            if player:
                player.wants_rematch = False
        logger.info("Room %s: offering a rematch", room.room_id)
        await room.broadcast_players(ServerPacket.REMATCH, b"")

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
            # Kept as raw bytes so the join reply can hand the same limits back
            # without this dictionary having to understand their shape.
            "limits": bytes(host.limits),
            "name": u16_to_string(packet.name),
            "password": u16_to_string(packet.password),
            "notes": bytes(packet.notes).split(b"\x00", 1)[0].decode("utf-8", errors="replace"),
        }

    @staticmethod
    def _encode_room_created(room: Room) -> bytes:
        return struct.pack("<I", room.room_id)

    @staticmethod
    def _encode_join_game(host_info: dict) -> bytes:
        """The room's settings, in the exact layout the client reads back.

        Filled into the same ctypes structure the client parses it with, so
        the two cannot disagree. Written out by hand as a format string it was
        twelve bytes short -- the deck size limits at the end were missing
        altogether -- and only the client ignoring this payload kept that from
        breaking every join.
        """
        duel_flags = int(host_info.get("duel_flags", 0) or 0)
        info = structs.HostInfo()
        info.banlist_hash = int(host_info.get("banlist_hash", host_info.get("lflist", 0)))
        info.allowed = int(host_info.get("allowed", 0))
        info.mode = int(host_info.get("mode", 0))
        info.duel_rule = int(host_info.get("duel_rule", host_info.get("rule", 5)))
        info.dont_check_deck_content = int(host_info.get("no_check_deck", 0))
        info.dont_shuffle_deck = int(host_info.get("no_shuffle_deck", 0))
        info.starting_lp = int(host_info.get("start_lp", 8000))
        info.starting_draw_count = int(host_info.get("start_hand", 5))
        info.draw_count_per_turn = int(host_info.get("draw_count", 1))
        info.time_limit_in_seconds = int(host_info.get("time_limit", 180))
        info.duel_flags_high = (duel_flags >> 32) & 0xFFFFFFFF
        info.duel_flags_low = duel_flags & 0xFFFFFFFF
        info.handshake = int(host_info.get("handshake") or 4043399681)
        info.version = _client_version(host_info.get("version"))
        info.t0_count = int(host_info.get("t0_count", 1))
        info.t1_count = int(host_info.get("t1_count", 1))
        info.best_of = int(host_info.get("best_of", 1))
        info.forbidden_types = int(host_info.get("forbidden_types", 0))
        info.extra_rules = int(host_info.get("extra_rules", 0))
        info.limits = _deck_limits(host_info.get("limits"))
        return bytes(info)
