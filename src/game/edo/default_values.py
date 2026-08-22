import ctypes
from core import variables
from game.edo import structs

DECK_LIMITS = structs.DeckLimits(
    structs.DeckLimits.Boundary(ctypes.c_uint16(40), ctypes.c_uint16(60)),
    structs.DeckLimits.Boundary(ctypes.c_uint16(0), ctypes.c_uint16(15)),
    structs.DeckLimits.Boundary(ctypes.c_uint16(0), ctypes.c_uint16(15))
)

# This duel flags indicate that we want to be the host.
DUEL_FLAGS = 4295157760


# host info for if the player wants to host
HOST_INFO = structs.HostInfo(
    banlist_hash=0,
    allowed=1,
    dont_check_deck_content=0,
    dont_shuffle_deck=0,
    starting_lp=8000,
    starting_draw_count=5,
    draw_count_per_turn=1,
    time_limit_in_seconds=600,
    duel_flags_high = DUEL_FLAGS >> 32,
    handshake=4043399681,
    version=variables.edo_client_version,
    t0_count=0,
    t1_count=0,
    best_of=1,
    duel_flags_low = DUEL_FLAGS & 0xFFFFFFFF,
    forbidden_types=0,
    extra_rules=0,
    limits=DECK_LIMITS
)



