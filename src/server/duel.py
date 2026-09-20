"""Duel state machine — orchestrates ocgcore and relays messages to players."""

import asyncio
import logging
import os
import struct

from server.core import (
    OcgCore, LOCATION_DECK, LOCATION_EXTRA, POS_FACEDOWN_ATTACK,
    OCG_DUEL_STATUS_END, OCG_DUEL_STATUS_AWAITING, OCG_DUEL_STATUS_CONTINUE,
)
from server.protocol import ServerPacket, RoomState
# Duel message ids come from the generated single source of truth
# (src/game/edo/message_constants.py, produced from ocgcore's ocgapi_constants.h).
# Never re-declare them here: a local copy silently drifts from the core and
# makes handlers parse the wrong message body.
from game.edo.message_constants import (
    MSG_CONFIRM_CARDS,
    MSG_DRAW,
    MSG_HINT,
    MSG_NEW_PHASE,
    MSG_NEW_TURN,
    MSG_SELECT_BATTLECMD,
    MSG_SELECT_CARD,
    MSG_SELECT_CHAIN,
    MSG_SELECT_COUNTER,
    MSG_SELECT_DISFIELD,
    MSG_SELECT_EFFECTYN,
    MSG_SELECT_IDLECMD,
    MSG_SELECT_OPTION,
    MSG_SELECT_PLACE,
    MSG_SELECT_POSITION,
    MSG_SELECT_SUM,
    MSG_SELECT_TRIBUTE,
    MSG_SELECT_UNSELECT_CARD,
    MSG_SELECT_YESNO,
    MSG_SHUFFLE_HAND,
    MSG_SHUFFLE_SET_CARD,
    MSG_SORT_CARD,
    MSG_START,
    MSG_SWAP_GRAVE_DECK,
    MSG_WIN,
)

logger = logging.getLogger(__name__)

# Messages that go to a specific player (first byte = player index)
PLAYER_ROUTED_MESSAGES = {
    MSG_SELECT_BATTLECMD, MSG_SELECT_IDLECMD, MSG_SELECT_EFFECTYN,
    MSG_SELECT_YESNO, MSG_SELECT_OPTION, MSG_SELECT_CARD, MSG_SELECT_CHAIN,
    MSG_SELECT_PLACE, MSG_SELECT_DISFIELD, MSG_SELECT_POSITION,
    MSG_SELECT_TRIBUTE, MSG_SELECT_COUNTER, MSG_SELECT_SUM,
    MSG_SELECT_UNSELECT_CARD, MSG_SORT_CARD, MSG_DRAW, MSG_CONFIRM_CARDS,
}


class DuelInstance:
    """Manages a single duel between two players."""

    def __init__(self, room, engine: OcgCore | None):
        self.room = room
        self.engine = engine
        self._duel_handle = None
        self._waiting_for_player: int = -1
        self._rps_choices: list[int] = [0, 0]
        self._turn_player: int = -1
        self._time_left = [180, 180]

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
        self._turn_player = conn.slot if go_first else (1 - conn.slot)

        order_data = struct.pack("B", self._turn_player)
        await self.room.broadcast_players(ServerPacket.ORDER_RESULT, order_data)

        await asyncio.sleep(0.3)
        await self._start_duel()

    async def _start_duel(self):
        """Load decks into ocgcore and begin."""
        if not self.engine:
            logger.error("No duel engine available")
            return

        self.room.state = RoomState.DUELING
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
            # Determine actual controller based on turn order
            controller = slot if self._turn_player == 0 else (1 - slot)
            self._load_deck(controller, player)

        self.engine.start_duel(self._duel_handle)
        await self._send_start_message()
        await self._process_loop()

    def _load_deck(self, controller: int, player):
        """Load player's deck into ocgcore."""
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
            data = struct.pack(
                "<BBIIHHHH",
                MSG_START,
                0,
                lp,
                lp,
                len(player.deck_main),
                len(player.deck_extra),
                len(opponent.deck_main) if opponent else 0,
                len(opponent.deck_extra) if opponent else 0,
            )
            await player.send(ServerPacket.GAME_MSG, data)

    async def _process_loop(self):
        """Main duel processing loop."""
        while True:
            status = self.engine.process(self._duel_handle)

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
            await self._send_game_message(msg_type, msg_data)

    async def _send_game_message(self, msg_type: int, msg_data: bytes):
        """Route a single game message to the appropriate player(s)."""
        if msg_type in PLAYER_ROUTED_MESSAGES and len(msg_data) > 1:
            target_player = msg_data[1]
            self._waiting_for_player = target_player
            # Send full message to target player
            target_conn = self._get_player_conn(target_player)
            if target_conn:
                await target_conn.send(ServerPacket.GAME_MSG, msg_data)
            # Send to opponent with possibly redacted info
            opponent = self._get_player_conn(1 - target_player)
            if opponent:
                await opponent.send(ServerPacket.GAME_MSG, msg_data)
            # Observers see everything
            for obs in self.room.observers:
                await obs.send(ServerPacket.GAME_MSG, msg_data)
        elif msg_type == MSG_WIN:
            await self.room.broadcast(ServerPacket.GAME_MSG, msg_data)
        elif msg_type == MSG_NEW_TURN and len(msg_data) > 1:
            self._turn_player = msg_data[1]
            await self.room.broadcast(ServerPacket.GAME_MSG, msg_data)
        else:
            # Broadcast to all
            await self.room.broadcast(ServerPacket.GAME_MSG, msg_data)

    def _get_player_conn(self, player_index: int):
        """Get connection for player by ocgcore player index."""
        if self._turn_player == 0:
            return self.room.players[player_index]
        else:
            return self.room.players[1 - player_index]

    async def handle_response(self, conn, payload: bytes):
        """Forward player response to ocgcore and continue processing."""
        if not self._duel_handle:
            return
        self.engine.set_response(self._duel_handle, payload)
        self._waiting_for_player = -1
        await self._process_loop()

    async def handle_surrender(self, conn):
        """Player surrenders."""
        if not self._duel_handle:
            return
        winner = 1 - conn.slot
        win_data = struct.pack("BB", winner, 0)  # winner, reason=surrender
        await self.room.broadcast(ServerPacket.GAME_MSG, bytes([MSG_WIN]) + win_data)
        await self._handle_duel_end()

    async def _handle_duel_end(self):
        """Clean up after duel ends."""
        self.room.state = RoomState.ENDED
        if self._duel_handle:
            self.engine.destroy_duel(self._duel_handle)
            self._duel_handle = None
        await self.room.broadcast_players(ServerPacket.DUEL_END, b"")
        logger.info("Duel ended in room %s", self.room.room_id)
