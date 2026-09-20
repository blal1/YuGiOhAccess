# Importing a module registers its @utils.duel_message_handler callbacks, so
# every handler module must be listed here. Ordered by message id; the ids
# themselves live in game.edo.message_constants, generated from ocgcore's
# ocgapi_constants.h, and the comments below are only a reading aid.
from ui.duel_messages import retry # noqa MSG_RETRY 1
from ui.duel_messages import hint # noqa MSG_HINT 2
from ui.duel_messages import waiting # noqa MSG_WAITING 3
from ui.duel_messages import start # noqa MSG_START 4
from ui.duel_messages import win # noqa MSG_WIN 5
from ui.duel_messages import update_data # noqa MSG_UPDATE_DATA 6
from ui.duel_messages import update_card # noqa MSG_UPDATE_CARD 7
from ui.duel_messages import select_battlecmd # noqa MSG_SELECT_BATTLECMD 10
from ui.duel_messages import idle # noqa MSG_SELECT_IDLECMD 11
from ui.duel_messages import select_effect_yes_or_no # noqa MSG_SELECT_EFFECTYN 12
from ui.duel_messages import select_yes_no # noqa MSG_SELECT_YESNO 13
from ui.duel_messages import select_option # noqa MSG_SELECT_OPTION 14
from ui.duel_messages import select_card # noqa MSG_SELECT_CARD 15, MSG_SELECT_TRIBUTE 20
from ui.duel_messages import select_chain # noqa MSG_SELECT_CHAIN 16
from ui.duel_messages import select_place # noqa MSG_SELECT_PLACE 18, MSG_SELECT_DISFIELD 24
from ui.duel_messages import select_position # noqa MSG_SELECT_POSITION 19
from ui.duel_messages import sort_chain # noqa MSG_SORT_CHAIN 21
from ui.duel_messages import select_counter # noqa MSG_SELECT_COUNTER 22
from ui.duel_messages import select_sum # noqa MSG_SELECT_SUM 23
from ui.duel_messages import sort_card # noqa MSG_SORT_CARD 25
from ui.duel_messages import select_unselect_card # noqa MSG_SELECT_UNSELECT_CARD 26
from ui.duel_messages import deck_top # noqa MSG_CONFIRM_DECKTOP 30, MSG_DECK_TOP 38
from ui.duel_messages import confirm_cards # noqa MSG_CONFIRM_CARDS 31
from ui.duel_messages import shuffle_deck # noqa MSG_SHUFFLE_DECK 32
from ui.duel_messages import shuffle_other # noqa MSG_SHUFFLE_HAND 33, MSG_SHUFFLE_EXTRA 39
from ui.duel_messages import swap_grave_deck # noqa MSG_SWAP_GRAVE_DECK 35
from ui.duel_messages import shuffle_set_card # noqa MSG_SHUFFLE_SET_CARD 36
from ui.duel_messages import reverse_deck # noqa MSG_REVERSE_DECK 37
from ui.duel_messages import new_turn # noqa MSG_NEW_TURN 40
from ui.duel_messages import phase # noqa MSG_NEW_PHASE 41
from ui.duel_messages import extra_deck_top # noqa MSG_CONFIRM_EXTRATOP 42
from ui.duel_messages import move # noqa MSG_MOVE 50
from ui.duel_messages import position_change # noqa MSG_POS_CHANGE 53
from ui.duel_messages import set # noqa MSG_SET 54
from ui.duel_messages import swap # noqa MSG_SWAP 55
from ui.duel_messages import field_disabled # noqa MSG_FIELD_DISABLED 56
from ui.duel_messages import summoning # noqa MSG_SUMMONING 60 .. MSG_SPSUMMONED 63
from ui.duel_messages import flip_summoning # noqa MSG_FLIPSUMMONING 64, MSG_FLIPSUMMONED 65
from ui.duel_messages import chaining # noqa MSG_CHAINING 70
from ui.duel_messages import chained # noqa MSG_CHAINED 71 .. MSG_CHAIN_DISABLED 76
from ui.duel_messages import card_selected # noqa MSG_CARD_SELECTED 80
from ui.duel_messages import random_selected # noqa MSG_RANDOM_SELECTED 81
from ui.duel_messages import become_target # noqa MSG_BECOME_TARGET 83
from ui.duel_messages import draw # noqa MSG_DRAW 90
from ui.duel_messages import damage_step_damage # noqa MSG_DAMAGE 91
from ui.duel_messages import recover # noqa MSG_RECOVER 92
from ui.duel_messages import equip # noqa MSG_EQUIP 93
from ui.duel_messages import lpupdate # noqa MSG_LPUPDATE 94
from ui.duel_messages import card_targetting # noqa MSG_CARD_TARGET 96, MSG_CANCEL_TARGET 97
from ui.duel_messages import pay_cost # noqa MSG_PAY_LPCOST 100
from ui.duel_messages import counters # noqa MSG_ADD_COUNTER 101, MSG_REMOVE_COUNTER 102
from ui.duel_messages import attack # noqa MSG_ATTACK 110
from ui.duel_messages import damage_step_battle # noqa MSG_BATTLE 111
from ui.duel_messages import attack_disabled # noqa MSG_ATTACK_DISABLED 112
from ui.duel_messages import damage_step_start # noqa MSG_DAMAGE_STEP_START 113
from ui.duel_messages import damage_step_end # noqa MSG_DAMAGE_STEP_END 114
from ui.duel_messages import missed_effect # noqa MSG_MISSED_EFFECT 120
from ui.duel_messages import toss # noqa MSG_TOSS_COIN 130, MSG_TOSS_DICE 131
from ui.duel_messages import rock_paper_scissors # noqa MSG_ROCK_PAPER_SCISSORS 132, MSG_HAND_RES 133
from ui.duel_messages import announce_race # noqa MSG_ANNOUNCE_RACE 140
from ui.duel_messages import announce_attrib # noqa MSG_ANNOUNCE_ATTRIB 141
from ui.duel_messages import announce_card # noqa MSG_ANNOUNCE_CARD 142
from ui.duel_messages import announce_number # noqa MSG_ANNOUNCE_NUMBER 143
from ui.duel_messages import card_hint # noqa MSG_CARD_HINT 160
from ui.duel_messages import tag_swap # noqa MSG_TAG_SWAP 161
from ui.duel_messages import reload_field # noqa MSG_RELOAD_FIELD 162
from ui.duel_messages import show_hint # noqa MSG_AI_NAME 163, MSG_SHOW_HINT 164
from ui.duel_messages import player_hint # noqa MSG_PLAYER_HINT 165
from ui.duel_messages import match_kill # noqa MSG_MATCH_KILL 170
from ui.duel_messages import remove_cards # noqa MSG_REMOVE_CARDS 190
# Ids this core declares but never emits: 8, 34, 95, 121, 122, 123, 180.
from ui.duel_messages import legacy_messages # noqa
