import struct
import ctypes

from game.edo.structs_utils import PASS_NAME_MAX_LENGTH, NOTES_MAX_LENGTH, CHAT_MSG_MAX_LENGTH, u16_to_string

class ClientIdType(ctypes.c_uint8):
    RESPONSE = 0x01
    UPDATE_DECK = 0x02
    RPS_CHOICE = 0x03
    TURN_CHOICE = 0x04
    PLAYER_INFO = 0x10
    CREATE_GAME = 0x11
    JOIN_GAME = 0x12
    LEAVE_GAME = 0x13
    SURRENDER = 0x14
    # Answers STOC_TIME_LIMIT. The server keeps counting our clock down until
    # it arrives, so not sending it can lose a duel on time.
    TIME_CONFIRM = 0x15
    CHAT = 0x16
    TO_DUELIST = 0x20
    TO_OBSERVER = 0x21
    READY = 0x22
    NOT_READY = 0x23
    TRY_KICK = 0x24
    TRY_START = 0x25
    REMATCH = 0xF0

class ServerIdType(ctypes.c_uint8):
    GAME_MSG      = 0x1
    ERROR_MSG     = 0x2
    CHOOSE_RPS    = 0x3
    CHOOSE_ORDER  = 0x4
    RPS_RESULT    = 0x5
    ORDER_RESULT  = 0x6
    CHANGE_SIDE   = 0x7
    WAITING_SIDE  = 0x8
    CREATE_GAME   = 0x11
    JOIN_GAME     = 0x12
    TYPE_CHANGE   = 0x13
    LEAVE_GAME    = 0x14
    DUEL_START    = 0x15
    DUEL_END      = 0x16
    REPLAY        = 0x17
    TIME_LIMIT    = 0x18
    # Chat as older servers send it; newer ones use CHAT_2 (0xF3).
    CHAT          = 0x19
    PLAYER_ENTER  = 0x20
    PLAYER_CHANGE = 0x21
    WATCH_CHANGE  = 0x22
    NEW_REPLAY    = 0x30
    CATCHUP       = 0xF0
    REMATCH       = 0xF1
    REMATCH_WAIT  = 0xF2
    CHAT_2        = 0xF3

server_id_type_to_name = {
    0x1: "GAME_MSG",
    0x2: "ERROR_MSG",
    0x3: "CHOOSE_RPS",
    0x4: "CHOOSE_ORDER",
    0x5: "RPS_RESULT",
    0x6: "ORDER_RESULT",
    0x7: "CHANGE_SIDE",
    0x8: "WAITING_SIDE",
    0x11: "CREATE_GAME",
    0x12: "JOIN_GAME",
    0x13: "TYPE_CHANGE",
    0x14: "LEAVE_GAME",
    0x15: "DUEL_START",
    0x16: "DUEL_END",
    0x17: "REPLAY",
    0x18: "TIME_LIMIT",
    0x20: "PLAYER_ENTER",
    0x21: "PLAYER_CHANGE",
    0x19: "CHAT",
    0x22: "WATCH_CHANGE",
    0x30: "NEW_REPLAY",
    0xF0: "CATCHUP",
    0xF1: "REMATCH",
    0xF2: "REMATCH_WAIT",
    0xF3: "CHAT_2",
}

class ClientVersion(ctypes.Structure):
    _fields_ = [
        ("client", ctypes.c_uint8 * 2),
        ("core", ctypes.c_uint8 * 2)
    ]

class DeckLimits(ctypes.Structure):
    class Boundary(ctypes.Structure):
        _fields_ = [
            ("min", ctypes.c_uint16),
            ("max", ctypes.c_uint16)
        ]

        def __repr__(self):
            return f"<Boundary min: {self.min} max: {self.max}>"

    _fields_ = [
        ("main", Boundary),
        ("extra", Boundary),
        ("side", Boundary)
    ]

    def __repr__(self):
        return f"<DeckLimits main: {self.main} extra: {self.extra} side: {self.side}>"

class Deck(ctypes.Structure):
    _fields_ = [
        ("main_length", ctypes.c_uint32),
        ("side_length", ctypes.c_uint32),
        ("main", ctypes.POINTER(ctypes.c_uint32)),
        ("side", ctypes.POINTER(ctypes.c_uint32))
    ]

    def set_main_deck(self, cards):
        cards_length = len(cards)
        array_type = ctypes.c_uint32 * cards_length
        self.main_array = array_type(*cards)
        self.main = self.main_array
        self.main_length = cards_length

    def set_side_deck(self, cards):
        cards_length = len(cards)
        array_type = ctypes.c_uint32 * cards_length
        self.side_array = array_type(*cards)
        self.side = self.side_array
        self.side_length = cards_length

    def __bytes__(self):
        return struct.pack('ii', self.main_length, self.side_length) + bytes(self.main_array) + bytes(self.side_array)

class HostInfo(ctypes.Structure):
    _fields_ = [
        ("banlist_hash", ctypes.c_uint32),
        ("allowed", ctypes.c_uint8),
        ("mode", ctypes.c_uint8),           # UNUSED
        ("duel_rule", ctypes.c_uint8),      # UNUSED
        ("dont_check_deck_content", ctypes.c_uint8),
        ("dont_shuffle_deck", ctypes.c_uint8),
        ("starting_lp", ctypes.c_uint32),
        ("starting_draw_count", ctypes.c_uint8),
        ("draw_count_per_turn", ctypes.c_uint8),
        ("time_limit_in_seconds", ctypes.c_uint16),
        ("duel_flags_high", ctypes.c_uint32),
        ("handshake", ctypes.c_uint32),
        ("version", ClientVersion),
        ("t0_count", ctypes.c_int32),
        ("t1_count", ctypes.c_int32),
        ("best_of", ctypes.c_int32),
        ("duel_flags_low", ctypes.c_uint32),
        ("forbidden_types", ctypes.c_int32),
        ("extra_rules", ctypes.c_uint16),
        ("limits", DeckLimits)
    ]

    def __repr__(self):
        s = '<HostInfo '
        for f, t in self._fields_:
            s += f"{f}: {getattr(self, f)} "
        s += ">"
        return s

class PlayerInfo(ctypes.Structure):
    _fields_ = [
        ("name", ctypes.c_uint16 * PASS_NAME_MAX_LENGTH),
    ]

class CreateGame(ctypes.Structure):
    _fields_ = [
        ("host_info", HostInfo),
        ("name", ctypes.c_uint16 * PASS_NAME_MAX_LENGTH),
        ("password", ctypes.c_uint16 * PASS_NAME_MAX_LENGTH),
        ("notes", ctypes.c_char * NOTES_MAX_LENGTH)
    ]

class JoinGame(ctypes.Structure):
    _fields_ = [
        ("version2", ctypes.c_uint16),
        ("id", ctypes.c_uint32),
        ("password", ctypes.c_uint16 * PASS_NAME_MAX_LENGTH),
        ("version", ClientVersion),
    ]

class Chat(ctypes.Structure):
    _fields_ = [
        ("msg", ctypes.c_uint16*CHAT_MSG_MAX_LENGTH),
    ]

class Chat2Type(ctypes.c_uint8):
    DUELIST = 0x1
    SPEC = 0x2
    SYSTEM = 0x3
    SYSTEM_ERROR = 0x4
    SYSTEM_SHOUT = 0x5


class StocChat2(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_uint8),
        ("is_team", ctypes.c_uint8),
        ("client_name", ctypes.c_uint16*20),
        ("msg", ctypes.c_uint16*256),
    ]

    def __repr__(self):
        return f"<StocChat2type: {self.type} is_team: {self.is_team} client_name: {u16_to_string(self.client_name)} msg: {u16_to_string(self.msg)}>"

class ErrorMSG(ctypes.Structure):
    _fields_ = [
        ("msg", ctypes.c_uint8),
        ("pad", ctypes.c_uint8),
        ("code", ctypes.c_uint32),
    ]

    def __repr__(self):
        return f"<ErrorMSG msg: {self.msg} code: {self.code}>"
    

class _Count(ctypes.Structure):
    _fields_ = [
        ('got', ctypes.c_uint32),
        ('min', ctypes.c_uint32),
        ('max', ctypes.c_uint32),
    ]

    def __repr__(self):
        return f"<_Count got: {self.got} min: {self.min} max: {self.max}>"

class DeckErrrorMSG(ctypes.Structure):
    _fields_ = [
        ("msg", ctypes.c_uint8),
        ("type", ctypes.c_uint32),
        ('count', _Count),
        ('code', ctypes.c_uint32),
                ]

    def __repr__(self):
        return f"<DeckErrrorMSG msg: {self.msg} type: {self.type} count: {self.count} code: {self.code}>"
    
class Ready(ctypes.Structure):
    _fields_ = []

class RPS:
    ROCK     = 0x1
    PAPER    = 0x2
    SCISSORS = 0x3

class RPSChoice(ctypes.Structure):
    _fields_ = [
        ('choice', ctypes.c_uint8),
    ]

class TurnChoice(ctypes.Structure):
    _fields_ = [
        ('choice', ctypes.c_uint8),
    ]

class StocCreateGame(ctypes.Structure):
    _fields_ = [
        ('id', ctypes.c_uint32),
    ]

    def __repr__(self):
        return f"<StocCreateGame id: {self.id}>"

class StocJoinGame(ctypes.Structure):
    _fields_ = [
        ('info', HostInfo),
    ]

    def __repr__(self):
        return f"<StocJoinGame {self.info}>"

class StocPlayerEnter(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('name', ctypes.c_uint16*20),
        ('pos', ctypes.c_uint8),
    ]

    def __repr__(self):
        return f"<StocPlayerEnter name: {u16_to_string(self.name)} pos: {self.pos}>"

class StocChangeType:
    SPECTATE  = 0x8
    READY     = 0x9
    NOT_READY = 0xA
    LEAVE     = 0xB

class StocPlayerChange(ctypes.Structure):
    _fields_ = [
        ('status', ctypes.c_uint8), # here it seems that pos is the first 4 bits and status the last 4 bits
    ]

    def __repr__(self):
        ready = self.status & 0xf
        pos = (self.status >> 4) & 0x0f
        return f"<StocPlayerChange {self.status:02x} pos: {pos} ready: {ready==StocChangeType.READY} not_ready: {ready==StocChangeType.NOT_READY} leave: {ready==StocChangeType.LEAVE} spectate: {ready==StocChangeType.SPECTATE}>"
    
    def is_ready(self):
        return self.status & 0xf == StocChangeType.READY
    
    def position(self):
        return (self.status >> 4) & 0x0f
    
class StocTypeChange(ctypes.Structure):
    _fields_ = [
        ('type', ctypes.c_uint8),
    ]

    def __repr__(self):
        pos = self.type & 0xf
        is_host = (self.type >> 4) & 0x0f
        return f"<StocTypeChange pos: {pos} is_host: {is_host}>"
    
    def is_host(self):
        return (self.type >> 4) & 0x0f
    
    def position(self):
        return self.type & 0xf

class StocRPSResult(ctypes.Structure):
    _fields_ = [
        ('result0', ctypes.c_uint8),
        ('result1', ctypes.c_uint8),
    ]

    def __repr__(self):
        result0 = ""
        if self.result0 == RPS.ROCK:
            result0 = "rock"
        elif self.result0 == RPS.PAPER:
            result0 = "paper"
        elif self.result0 == RPS.SCISSORS:
            result0 = "scissors"
        result1 = ""
        if self.result1 == RPS.ROCK:
            result1 = "rock"
        elif self.result1 == RPS.PAPER:
            result1 = "paper"
        elif self.result1 == RPS.SCISSORS:
            result1 = "scissors"
        return f"<StocRPSResult result0: {result0} result1: {result1}>"

class StocTimeLimit(ctypes.Structure):
    _fields_ = [
        ('team', ctypes.c_uint8),
        ('time', ctypes.c_uint16),
    ]

    def __repr__(self):
        return f"<StocTimeLimit team: {self.team} time: {self.time} seconds>"

class StocWatchChange(ctypes.Structure):
    """STOC_HS_WATCH_CHANGE: how many spectators are now watching the room."""
    _pack_ = 1
    _fields_ = [
        ('watch_count', ctypes.c_uint16),
    ]

    def __repr__(self):
        return f"<StocWatchChange watch_count: {self.watch_count}>"

class StocCatchUp(ctypes.Structure):
    """STOC_CATCHUP: 1 while the server fast forwards a joiner, 0 once live."""
    _pack_ = 1
    _fields_ = [
        ('catching_up', ctypes.c_uint8),
    ]

    def __repr__(self):
        return f"<StocCatchUp catching_up: {bool(self.catching_up)}>"


class StocChat(ctypes.Structure):
    """STOC_CHAT: the pre CHAT_2 chat packet, still sent by older servers.

    ``player`` is a seat index rather than a name; anything at or above the
    number of duelists is an observer or the server itself.
    """
    _pack_ = 1
    _fields_ = [
        ('player', ctypes.c_uint16),
        ('msg', ctypes.c_uint16 * 256),
    ]

    def __repr__(self):
        return f"<StocChat player: {self.player}>"


class CtosKick(ctypes.Structure):
    """CTOS_HS_KICK: the host removes whoever sits at this position."""
    _pack_ = 1
    _fields_ = [
        ('pos', ctypes.c_uint8),
    ]

    def __repr__(self):
        return f"<CtosKick pos: {self.pos}>"
