"""Duel state machine — orchestrates ocgcore and relays messages to players."""

import asyncio
import logging
import os
import struct

from server.core import (
    OcgCore, LOCATION_DECK, LOCATION_EXTRA, LOCATION_GRAVE, LOCATION_HAND,
    LOCATION_MZONE, LOCATION_REMOVED, LOCATION_SZONE, POS_FACEDOWN_ATTACK,
    OCG_DUEL_STATUS_END, OCG_DUEL_STATUS_AWAITING, OCG_DUEL_STATUS_CONTINUE,
)
from server.protocol import ServerPacket, RoomState
from server import prompt_debug, visibility
from server.replay import DuelReplay
# Duel message ids come from the generated single source of truth
# (src/game/edo/message_constants.py, produced from ocgcore's ocgapi_constants.h).
# Never re-declare them here: a local copy silently drifts from the core and
# makes handlers parse the wrong message body.
from game.edo.message_constants import (
    MSG_DRAW,
    MSG_MOVE,
    MSG_NEW_TURN,
    MSG_RETRY,
    MSG_SHUFFLE_EXTRA,
    MSG_SHUFFLE_HAND,
    MSG_START,
    MSG_UPDATE_DATA,
    MSG_WAITING,
    MSG_WIN,
    # Re-exported rather than used here. An earlier version of this module
    # carried its own id table which had drifted from the core (it gave 60 to
    # MSG_SWAP_GRAVE_DECK, which is MSG_SUMMONING), and reading these three
    # off this module is how the test suite proves that table is gone.
    MSG_CONFIRM_CARDS,  # noqa: F401
    MSG_SHUFFLE_SET_CARD,  # noqa: F401
    MSG_SWAP_GRAVE_DECK,  # noqa: F401
)
# Which messages belong to a single player is shared with the client, so the two
# sides can never disagree about who a prompt was for.
from game.edo.message_routing import (
    PLAYER_INFO_MESSAGES,
    PROMPT_MESSAGES,
    message_name,
)

logger = logging.getLogger(__name__)

# Prompts reach only the player they address; the other seat gets MSG_WAITING,
# the way the upstream EDOPro server says "it is not your move". Sending them to
# both let each client answer for the other -- the bot took the human's turns,
# and the human was shown the bot's hand in card menus.
PLAYER_ROUTED_MESSAGES = PROMPT_MESSAGES | PLAYER_INFO_MESSAGES

# Messages that carry card codes the recipient may not be entitled to see.
REDACTED_MESSAGES = {MSG_DRAW, MSG_MOVE, MSG_SHUFFLE_HAND, MSG_SHUFFLE_EXTRA}

# The locations the client renders. The deck is deliberately absent: nobody may
# see it, and its order is not the player's to know.
REFRESHED_LOCATIONS = (
    LOCATION_MZONE, LOCATION_SZONE, LOCATION_HAND, LOCATION_EXTRA,
    LOCATION_GRAVE, LOCATION_REMOVED,
)

# Everything the client's query parser understands and uses to draw a card.
# QUERY_IS_PUBLIC is requested explicitly: redaction keys on it, and current
# ocgcore builds only emit it unconditionally as a temporary workaround.
REFRESH_QUERY_FLAGS = (
    0x1          # CODE
    | 0x2        # POSITION
    | 0x4        # ALIAS
    | 0x8        # TYPE
    | 0x10       # LEVEL
    | 0x20       # RANK
    | 0x40       # ATTRIBUTE
    | 0x80       # RACE
    | 0x100      # ATTACK
    | 0x200      # DEFENSE
    | 0x400      # BASE_ATTACK
    | 0x800      # BASE_DEFENSE
    | 0x10000    # OVERLAY_CARD
    | 0x20000    # COUNTERS
    | 0x100000   # IS_PUBLIC
    | 0x200000   # LSCALE
    | 0x400000   # RSCALE
    | 0x800000   # LINK
)


class DuelInstance:
    """Manages a single duel between two players."""

    def __init__(self, room, engine: OcgCore | None):
        self.room = room
        self.engine = engine
        self._duel_handle = None
        self._waiting_for_player: int = -1
        # Who the last prompt went to. Unlike _waiting_for_player this survives
        # the response, so a MSG_RETRY that arrives once the answer was already
        # handed to the core still knows whose answer was rejected.
        self._last_prompt_player: int = -1
        # Last field state each viewer was told about, keyed by
        # (viewer, controller, location). A prompt during a long chain would
        # otherwise resend an unchanged hand a dozen times, and every one of
        # those rebuilds the client's card lists mid-speech.
        self._sent_field_state: dict = {}
        # Set once a winner is known. The core will happily keep asking for
        # decisions after it has announced one, and the client has already torn
        # its duel state down by then, so every further prompt came back
        # cancelled and produced another winner announcement.
        self._finished = False
        self._rps_choices: list[int] = [0, 0]
        # Room slot of the player who goes first. The core always calls that
        # player 0, so this single value defines the slot <-> core mapping for
        # the whole duel. It must never be derived from whose turn it is: the
        # turn alternates, the seating does not.
        self._first_player_slot: int = 0
        # Core index of the player whose turn it is. Informational only.
        self._turn_player: int = -1
        # Each player's clock, by core player index, and when the clock
        # currently running was started. The client shows a countdown; until
        # the server told it anything it counted down from a default it had
        # invented, which bore no relation to the room's time limit.
        self._time_limit = max(0, int(room.host_info.get("time_limit", 180) or 0))
        self._time_left = [self._time_limit, self._time_limit]
        self._clock_started_at: float | None = None
        # Everything the core says, kept so the duel can be handed back to the
        # players when it ends. Both sides declared the replay packets and
        # neither ever sent one.
        self._replay = DuelReplay()

    # -- seat mapping ------------------------------------------------------

    def set_first_player_slot(self, slot: int):
        self._first_player_slot = 1 if slot else 0
        self._turn_player = 0
        logger.info(
            "Duel seating: room slot %d goes first (core player 0), slot %d is core player 1",
            self._first_player_slot, 1 - self._first_player_slot,
        )

    def slot_to_core_player(self, slot: int) -> int:
        return 0 if slot == self._first_player_slot else 1

    def core_player_to_slot(self, core_player: int) -> int:
        return self._first_player_slot if core_player == 0 else 1 - self._first_player_slot

    async def start_rps(self):
        """Send RPS choice prompt to both players."""
        self.room.state = RoomState.RPS
        self._rps_choices = [0, 0]
        for p in self.room.players:
            if p:
                await p.send(ServerPacket.CHOOSE_RPS, b"")

    async def handle_rps_choice(self, conn, payload: bytes):
        if conn.slot < 0 or conn.slot > 1:
            return
        choice = payload[0] if payload else 1
        self._rps_choices[conn.slot] = choice

        if all(c > 0 for c in self._rps_choices):
            await self._resolve_rps()

    async def _resolve_rps(self):
        c0, c1 = self._rps_choices
        result_data = struct.pack("BB", c0, c1)
        await self.room.broadcast_players(ServerPacket.RPS_RESULT, result_data)

        if c0 == c1:
            # Tie — replay
            self._rps_choices = [0, 0]
            await asyncio.sleep(0.5)
            await self.start_rps()
        else:
            # Winner chooses turn order
            # RPS: 1=scissors, 2=rock, 3=paper
            winner = 0 if (c0 == 2 and c1 == 1) or (c0 == 3 and c1 == 2) or (c0 == 1 and c1 == 3) else 1
            self.room.state = RoomState.CHOOSING_ORDER
            await self.room.players[winner].send(ServerPacket.CHOOSE_ORDER, b"")

    async def handle_turn_choice(self, conn, payload: bytes):
        """Player chose to go first (1) or second (0)."""
        if conn.slot < 0:
            return
        go_first = payload[0] if payload else 1
        self.set_first_player_slot(conn.slot if go_first else (1 - conn.slot))

        order_data = struct.pack("B", self._first_player_slot)
        await self.room.broadcast_players(ServerPacket.ORDER_RESULT, order_data)

        await asyncio.sleep(0.3)
        await self._start_duel()

    async def _start_duel(self):
        """Load decks into ocgcore and begin."""
        if not self.engine:
            logger.error("No duel engine available")
            return

        self.room.state = RoomState.DUELING
        self._sent_field_state.clear()
        self._finished = False
        seed = int.from_bytes(os.urandom(8), "little")
        host_info = self.room.host_info

        flags = host_info.get("duel_flags", 0)
        lp = host_info.get("start_lp", 8000)
        draw_count = host_info.get("draw_count", 1)
        start_hand = host_info.get("start_hand", 5)

        self._duel_handle = self.engine.create_duel(
            seed=seed, flags=flags, lp=lp, draw_count=draw_count, start_count=start_hand
        )

        # Load decks for both players
        for slot in range(2):
            player = self.room.players[slot]
            if not player:
                continue
            controller = self.slot_to_core_player(slot)
            logger.debug(
                "Loading deck for %s (slot %d) as core player %d: %d main, %d extra",
                player.name, slot, controller, len(player.deck_main), len(player.deck_extra),
            )
            self._load_deck(controller, player)

        self.engine.start_duel(self._duel_handle)
        await self._send_start_message()
        await self._refresh_field("the opening hand")
        await self._process_loop()

    def _load_deck(self, controller: int, player):
        """Load player's deck into ocgcore."""
        if self.engine is None or self._duel_handle is None:
            # Only reachable if a caller skips _start_duel's own check; say so
            # rather than failing inside ctypes with a null handle.
            logger.error("Asked to load a deck with no duel running")
            return
        for i, card_id in enumerate(player.deck_main):
            self.engine.new_card(
                self._duel_handle, card_id, controller, controller,
                LOCATION_DECK, i, POS_FACEDOWN_ATTACK
            )
        for i, card_id in enumerate(player.deck_extra):
            self.engine.new_card(
                self._duel_handle, card_id, controller, controller,
                LOCATION_EXTRA, i, POS_FACEDOWN_ATTACK
            )

    async def _send_start_message(self):
        host_info = self.room.host_info
        lp = int(host_info.get("start_lp", 8000))
        for slot, player in enumerate(self.room.players):
            if not player:
                continue
            opponent = self.room.players[1 - slot]
            # Byte 1 is the recipient's own core player index. Hardcoding 0 told
            # both clients "you are player 0", so every controller byte that
            # followed was read from the wrong side of the field.
            core_player = self.slot_to_core_player(slot)
            data = struct.pack(
                "<BBIIHHHH",
                MSG_START,
                core_player,
                lp,
                lp,
                len(player.deck_main),
                len(player.deck_extra),
                len(opponent.deck_main) if opponent else 0,
                len(opponent.deck_extra) if opponent else 0,
            )
            logger.info(
                "MSG_START -> %s (slot %d) as core player %d",
                player.name, slot, core_player,
            )
            await player.send(ServerPacket.GAME_MSG, data)

    async def _process_loop(self):
        """Main duel processing loop."""
        while True:
            if self._finished:
                break
            status = self.engine.process(self._duel_handle)
            logger.debug("ocgcore process -> status %s", status)

            if status == OCG_DUEL_STATUS_END:
                await self._handle_duel_end()
                break
            elif status == OCG_DUEL_STATUS_AWAITING:
                msg_buffer = self.engine.get_message(self._duel_handle)
                if msg_buffer:
                    await self._route_messages(msg_buffer)
                # Wait for player response
                break
            elif status == OCG_DUEL_STATUS_CONTINUE:
                msg_buffer = self.engine.get_message(self._duel_handle)
                if msg_buffer:
                    await self._route_messages(msg_buffer)
                await asyncio.sleep(0)  # yield to event loop

    async def _route_messages(self, msg_buffer: bytes):
        """Parse and route game messages from ocgcore to appropriate players."""
        offset = 0
        while offset < len(msg_buffer):
            if offset + 1 > len(msg_buffer):
                break

            msg_len = struct.unpack_from("<I", msg_buffer, offset)[0]
            offset += 4
            if offset + msg_len > len(msg_buffer):
                break

            msg_data = msg_buffer[offset:offset + msg_len]
            offset += msg_len

            if not msg_data:
                continue

            msg_type = msg_data[0]
            logger.debug(
                "Core message %s (%d bytes): %s",
                message_name(msg_type), len(msg_data), msg_data[:32].hex(),
            )
            # Recorded before routing, so the replay holds the duel as the
            # core told it rather than as one seat was allowed to see it.
            self._replay.add(msg_data)
            await self._send_game_message(msg_type, msg_data)

    async def _send_game_message(self, msg_type: int, msg_data: bytes):
        """Route a single game message to the appropriate player(s)."""
        if msg_type in PROMPT_MESSAGES and len(msg_data) > 1:
            await self._send_prompt(msg_type, msg_data)
        elif msg_type == MSG_RETRY:
            # Only the player whose answer the core rejected should be asked
            # again; broadcasting it made both seats re-prompt in turn, which is
            # what flipped the card menu between the two hands.
            await self._send_to_core_player(self._last_prompt_player, msg_type, msg_data)
        elif msg_type in PLAYER_INFO_MESSAGES and len(msg_data) > 1:
            await self._broadcast(msg_type, msg_data)
        elif msg_type == MSG_WIN:
            self._finished = True
            logger.info("Duel won; no further prompts will be sent")
            if len(msg_data) > 1:
                self._record_result(msg_data[1])
            await self._broadcast(msg_type, msg_data)
            await self._handle_duel_end()
        elif msg_type == MSG_NEW_TURN and len(msg_data) > 1:
            # msg_data[1] is a CORE player index, not a room slot. Storing it in
            # the seat mapping used to swap both players' identities from the
            # second turn onwards.
            self._turn_player = msg_data[1]
            logger.info(
                "MSG_NEW_TURN: core player %d (room slot %d)",
                self._turn_player, self.core_player_to_slot(self._turn_player),
            )
            await self._broadcast(msg_type, msg_data)
        else:
            await self._broadcast(msg_type, msg_data)

    # -- catching a latecomer up -------------------------------------------

    async def catch_up(self, conn):
        """Replay the duel so far to somebody who just started watching.

        A spectator who joined mid duel used to see an empty screen until the
        next thing happened, and then only fragments. The client has always
        known how to be caught up -- it hushes the burst and summarises it --
        but nothing ever sent it.
        """
        if self._duel_handle is None or self._finished:
            logger.debug("Nothing to catch %s up on", getattr(conn, "name", "an observer"))
            return
        recorded = list(self._replay._messages)
        logger.info(
            "Catching %s up on %d message(s) in room %s",
            getattr(conn, "name", "an observer"), len(recorded), self.room.room_id,
        )
        await conn.send(ServerPacket.DUEL_START, b"")
        await conn.send(ServerPacket.CATCHUP, bytes([1]))
        for msg_data in recorded:
            await conn.send(ServerPacket.GAME_MSG, self._for_spectator(msg_data))
        await conn.send(ServerPacket.CATCHUP, bytes([0]))
        # The board state itself is ours, not the core's, so it is not in the
        # recording; ask for it again now that somebody new is watching.
        self._sent_field_state = {
            key: value for key, value in self._sent_field_state.items() if key[0] is not conn
        }
        await self._refresh_field("a new spectator")

    @staticmethod
    def _for_spectator(msg_data: bytes) -> bytes:
        """One recorded message, as a spectator is allowed to see it."""
        if not msg_data:
            return msg_data
        msg_type = msg_data[0]
        if msg_type == MSG_START and len(msg_data) > 1:
            # Byte 1 says which seat the recipient holds. A spectator holds
            # none, which is what the high bits mean.
            return bytes([msg_data[0], 0x10]) + msg_data[2:]
        if msg_type in REDACTED_MESSAGES:
            return visibility.redact_message(msg_type, msg_data, visibility.NO_SEAT)
        return msg_data

    # -- the turn clock ----------------------------------------------------

    async def _start_clock(self, core_player: int, conn):
        """Tell a player how long they have, and start counting.

        The client runs the countdown the player hears; all it needs from here
        is the truth about where the clock stands. Without this it counted
        down from a built in default that had nothing to do with the room.
        """
        if not self._time_limit or not (0 <= core_player < 2):
            return
        self._clock_started_at = asyncio.get_running_loop().time()
        await conn.send(
            ServerPacket.TIME_LIMIT,
            struct.pack("<BH", core_player, self._time_left[core_player]),
        )

    def _stop_clock(self, core_player: int):
        """Charge the time a player spent thinking to their clock."""
        if not self._time_limit or self._clock_started_at is None:
            return
        if not (0 <= core_player < 2):
            self._clock_started_at = None
            return
        elapsed = asyncio.get_running_loop().time() - self._clock_started_at
        self._clock_started_at = None
        remaining = self._time_left[core_player] - int(elapsed)
        # The clock stops at zero rather than running a player out of the
        # duel: this server exists for practice, and losing a solo game to the
        # clock while reading a card aloud would be its own accessibility bug.
        self._time_left[core_player] = max(0, remaining)

    async def _send_prompt(self, msg_type: int, msg_data: bytes):
        """Send a prompt to the one player it addresses; the other one waits."""
        if self._finished:
            logger.debug("Dropping %s: the duel is already over", message_name(msg_type))
            return
        # A prompt is the only moment a client has to act on its board, so the
        # board is brought up to date first. The core never volunteers this; it
        # has to be asked.
        await self._refresh_field(message_name(msg_type))
        target_player = msg_data[1]
        self._waiting_for_player = target_player
        self._last_prompt_player = target_player
        target_slot = self.core_player_to_slot(target_player)
        target_conn = self.room.players[target_slot] if 0 <= target_slot < 2 else None

        logger.info(
            "Prompt %s -> core player %d / room slot %d (%s)",
            message_name(msg_type), target_player, target_slot,
            target_conn.name if target_conn else "nobody",
        )
        offer = prompt_debug.summarise(msg_type, msg_data)
        if offer is not None:
            # What the core is actually offering. A player that then does
            # nothing either was offered nothing, or did not understand what it
            # was offered, and only this line tells the two apart.
            logger.info("  offering: %s", offer)
        if target_conn:
            await self._start_clock(target_player, target_conn)
            await target_conn.send(ServerPacket.GAME_MSG, msg_data)
        else:
            logger.error(
                "Prompt %s addressed core player %d but no connection holds that seat",
                message_name(msg_type), target_player,
            )

        other = self.room.players[1 - target_slot] if 0 <= target_slot < 2 else None
        if other:
            logger.debug("MSG_WAITING -> slot %d (%s)", 1 - target_slot, other.name)
            await other.send(ServerPacket.GAME_MSG, bytes([MSG_WAITING]))

        for obs in self.room.observers:
            await obs.send(ServerPacket.GAME_MSG, msg_data)

    async def _send_to_core_player(self, core_player: int, msg_type: int, msg_data: bytes):
        if core_player < 0:
            logger.warning(
                "%s arrived while no player was being awaited; broadcasting it",
                message_name(msg_type),
            )
            await self._broadcast(msg_type, msg_data)
            return
        slot = self.core_player_to_slot(core_player)
        conn = self.room.players[slot] if 0 <= slot < 2 else None
        logger.info(
            "%s -> core player %d / room slot %d (%s)",
            message_name(msg_type), core_player, slot, conn.name if conn else "nobody",
        )
        if conn:
            await conn.send(ServerPacket.GAME_MSG, msg_data)
        for obs in self.room.observers:
            await obs.send(ServerPacket.GAME_MSG, msg_data)

    async def _refresh_field(self, reason: str = ""):
        """Send every player a MSG_UPDATE_DATA for each rendered location.

        Each recipient gets its own copy: the controller of a location sees it
        whole, everyone else gets the identities of non public cards blanked.
        """
        if not self._duel_handle or not self.engine:
            return
        for controller in (0, 1):
            for location in REFRESHED_LOCATIONS:
                try:
                    buffer = self.engine.query_location(
                        self._duel_handle, REFRESH_QUERY_FLAGS, controller, location
                    )
                except Exception:
                    logger.exception(
                        "Query failed for core player %d location 0x%02X", controller, location
                    )
                    continue
                if not buffer:
                    continue
                await self._send_update_data(controller, location, buffer)
        logger.debug("Field refreshed%s", f" before {reason}" if reason else "")

    async def _send_update_data(self, controller: int, location: int, buffer: bytes):
        """Wrap a query buffer as MSG_UPDATE_DATA and send it to each viewer."""
        for slot, player in enumerate(self.room.players):
            if not player:
                continue
            recipient = self.slot_to_core_player(slot)
            payload = visibility.redact_query_buffer(buffer, reveal=recipient == controller)
            await self._send_field_state(player, slot, controller, location, payload)
        if self.room.observers:
            # A spectator holds no seat, so nothing private is theirs to see.
            payload = visibility.redact_query_buffer(buffer, reveal=False)
            for obs in self.room.observers:
                # Keyed by the connection itself rather than its position in
                # the list: an observer leaving used to shift everyone after
                # them onto somebody else's record of what had been sent.
                await self._send_field_state(obs, obs, controller, location, payload)

    async def _send_field_state(self, conn, viewer, controller: int, location: int, payload: bytes):
        key = (viewer, controller, location)
        if self._sent_field_state.get(key) == payload:
            return
        self._sent_field_state[key] = payload
        # The query buffer already opens with its own length word, which is the
        # size field the client reads. Adding another one here shifted every
        # chunk by four bytes and the whole message failed to parse.
        await conn.send(
            ServerPacket.GAME_MSG,
            struct.pack("<BBB", MSG_UPDATE_DATA, controller, location) + payload,
        )

    async def _broadcast(self, msg_type: int, msg_data: bytes):
        if msg_type in REDACTED_MESSAGES:
            await self._broadcast_redacted(msg_type, msg_data)
            return
        logger.debug("%s -> everyone", message_name(msg_type))
        await self.room.broadcast(ServerPacket.GAME_MSG, msg_data)

    async def _broadcast_redacted(self, msg_type: int, msg_data: bytes):
        """Send a message that carries card codes, one tailored copy each."""
        logger.debug("%s -> everyone, redacted per seat", message_name(msg_type))
        for slot, player in enumerate(self.room.players):
            if not player:
                continue
            recipient = self.slot_to_core_player(slot)
            await player.send(
                ServerPacket.GAME_MSG,
                visibility.redact_message(msg_type, msg_data, recipient),
            )
        for obs in self.room.observers:
            await obs.send(
                ServerPacket.GAME_MSG,
                visibility.redact_message(msg_type, msg_data, visibility.NO_SEAT),
            )

    def _get_player_conn(self, player_index: int):
        """Get connection for player by ocgcore player index."""
        slot = self.core_player_to_slot(player_index)
        return self.room.players[slot] if 0 <= slot < 2 else None

    async def handle_response(self, conn, payload: bytes):
        """Forward player response to ocgcore and continue processing."""
        if self._finished or not self._duel_handle:
            logger.debug("Response from %s dropped: no duel running", conn.name)
            return
        if not self._is_expected_responder(conn):
            logger.warning(
                "Ignoring response from %s (slot %d): the core is waiting on core "
                "player %d (room slot %d). Payload: %s",
                conn.name, conn.slot, self._waiting_for_player,
                self.core_player_to_slot(self._waiting_for_player)
                if self._waiting_for_player >= 0 else -1,
                payload.hex(),
            )
            return
        logger.info(
            "Response from %s (slot %d) for core player %d: %s",
            conn.name, conn.slot, self._waiting_for_player, payload.hex(),
        )
        self.engine.set_response(self._duel_handle, payload)
        self._stop_clock(self._waiting_for_player)
        self._waiting_for_player = -1
        await self._process_loop()

    def _is_expected_responder(self, conn) -> bool:
        """Only the player the core is blocked on may answer.

        Without this the bot's answer could be consumed for the human's prompt
        (and the reverse), which is how moves appeared to be made for the user.
        """
        if self._waiting_for_player < 0:
            return False
        expected_slot = self.core_player_to_slot(self._waiting_for_player)
        return 0 <= expected_slot < 2 and self.room.players[expected_slot] is conn

    async def handle_surrender(self, conn):
        """Player surrenders."""
        if not self._duel_handle:
            return
        if not (0 <= conn.slot < 2) or self.room.players[conn.slot] is not conn:
            # A spectator holds no seat, so ``1 - conn.slot`` was 2, and the
            # duel was handed to a player who does not exist. Nobody but a
            # duelist can give a duel up.
            logger.warning(
                "Ignoring a surrender from %s, who holds no seat in room %s",
                conn.name or "an observer", self.room.room_id,
            )
            return
        # MSG_WIN names a core player, not a room slot. Sending the slot handed
        # the duel to whoever happened to sit opposite in the room, so giving up
        # during the opponent's turn announced the surrendering player as winner.
        winner = self.slot_to_core_player(1 - conn.slot)
        logger.info(
            "%s (slot %d) surrendered; core player %d wins",
            conn.name, conn.slot, winner,
        )
        win_data = struct.pack("BB", winner, 0)  # winner, reason=surrender
        self._finished = True
        self._record_result(winner)
        await self.room.broadcast(ServerPacket.GAME_MSG, bytes([MSG_WIN]) + win_data)
        await self._handle_duel_end()

    @property
    def is_finished(self) -> bool:
        return self._finished

    def _record_result(self, winning_core_player: int):
        """Note who took this game, for the match score.

        MSG_WIN names a core player, and 2 means a draw. The room keeps score
        by seat, so this is the one place the two are reconciled.
        """
        self.room.games_played += 1
        if winning_core_player not in (0, 1):
            logger.info("Game %d in room %s was a draw", self.room.games_played, self.room.room_id)
            return
        slot = self.core_player_to_slot(winning_core_player)
        if 0 <= slot < 2:
            self.room.match_wins[slot] += 1
        logger.info(
            "Game %d in room %s: slot %d won, match score %s",
            self.room.games_played, self.room.room_id, slot, self.room.match_wins,
        )

    async def _handle_duel_end(self):
        """Clean up after duel ends."""
        self._finished = True
        self._clock_started_at = None
        if self._duel_handle:
            self.engine.destroy_duel(self._duel_handle)
            self._duel_handle = None
        await self.room.broadcast_players(ServerPacket.DUEL_END, b"")
        logger.info("Duel ended in room %s", self.room.room_id)

        if self.room.is_match and not self.room.match_is_decided():
            await self._begin_side_decking()
            return
        self.room.state = RoomState.ENDED
        await self._send_replay()
        lobby = getattr(self.room, "lobby", None)
        if lobby is not None:
            # Nothing ever asked, so the client's rematch screen -- which has
            # been there all along -- could never appear.
            await lobby.offer_rematch(self.room)

    async def _send_replay(self):
        """Hand each player the duel they just played, as a replay file.

        The core keeps the authoritative record; until this existed the
        REPLAY packets were declared on both sides and never sent, so an
        offline duel left nothing behind at all.
        """
        replay = self._replay.to_bytes() if self._replay is not None else b""
        if not replay:
            logger.debug("No replay recorded for room %s", self.room.room_id)
            return
        logger.info("Sending a %d byte replay to room %s", len(replay), self.room.room_id)
        await self.room.broadcast_players(ServerPacket.NEW_REPLAY, replay)

    async def _begin_side_decking(self):
        """Ask both players for their deck again before the next game.

        The client has had the side deck screen all along; nothing ever asked
        it to show it, so a best-of-three stopped dead after game one.
        """
        self.room.state = RoomState.SIDE_DECKING
        self.room.awaiting_side_deck = {
            slot for slot, player in enumerate(self.room.players) if player
        }
        logger.info(
            "Room %s: side decking before game %d of %d",
            self.room.room_id, self.room.games_played + 1, self.room.best_of,
        )
        for slot in sorted(self.room.awaiting_side_deck):
            player = self.room.players[slot]
            if player:
                await player.send(ServerPacket.CHANGE_SIDE, b"")
        lobby = getattr(self.room, "lobby", None)
        if lobby is not None:
            # A bot never answers this, so it is excused here rather than
            # holding the match up for a side deck that will never arrive.
            await lobby._complete_side_decking_for_bots(self.room)
