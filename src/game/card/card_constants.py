from enum import IntFlag, unique

from core.i18n import _

ATTRIBUTES_OFFSET = 1010
RACES_OFFSET = 1020

AMOUNT_ATTRIBUTES = 7
AMOUNT_RACES = 30


@unique
class TYPE(IntFlag):
    MONSTER = 0x1
    SPELL = 0x2
    TRAP = 0x4
    NORMAL = 0x10
    EFFECT = 0x20
    FUSION = 0x40
    RITUAL = 0x80
    TRAPMONSTER = 0x100
    SPIRIT = 0x200
    UNION = 0x400
    DUAL = 0x800
    TUNER = 0x1000
    SYNCHRO = 0x2000
    TOKEN = 0x4000
    QUICKPLAY = 0x10000
    CONTINUOUS = 0x20000
    EQUIP = 0x40000
    FIELD = 0x80000
    COUNTER = 0x100000
    FLIP = 0x200000
    TOON = 0x400000
    XYZ = 0x800000
    PENDULUM = 0x1000000
    SPSUMMON = 0x2000000
    LINK = 0x4000000
    # for this mud only
    EXTRA = XYZ | SYNCHRO | FUSION | LINK

@unique
class LOCATION(IntFlag):
    DECK = 0x1
    HAND = 0x2
    MONSTER_ZONE = 0x4
    SPELL_AND_TRAP_ZONE = 0x8
    GRAVE = 0x10
    REMOVED = 0x20
    EXTRA = 0x40
    OVERLAY = 0x80
    ONFIELD = MONSTER_ZONE | SPELL_AND_TRAP_ZONE
    FIELD_ZONE = 0x100
    PENDULUM_ZONE = 0x200

@unique
class POSITION(IntFlag):
    FACE_UP_ATTACK = 0x1
    FACE_DOWN_ATTACK = 0x2
    FACE_UP_DEFENSE = 0x4
    FACE_UP = FACE_UP_ATTACK | FACE_UP_DEFENSE
    FACE_DOWN_DEFENSE = 0x8
    FACE_DOWN = FACE_DOWN_ATTACK | FACE_DOWN_DEFENSE
    ATTACK = FACE_UP_ATTACK | FACE_DOWN_ATTACK
    DEFENSE = FACE_UP_DEFENSE | FACE_DOWN_DEFENSE


LINK_MARKERS = {
    0o0001: _("bottom left"),
    0o0002: _("bottom"),
    0o0004: _("bottom right"),
    0o0010: _("left"),
    0o0040: _("right"),
    0o0100: _("top left"),
    0o0200: _("top"),
    0o0400: _("top right"),
}

@unique
class QUERY(IntFlag):
    CODE = 0x1
    POSITION = 0x2
    ALIAS = 0x4
    TYPE = 0x8
    LEVEL = 0x10
    RANK = 0x20
    ATTRIBUTE = 0x40
    RACE = 0x80
    ATTACK = 0x100
    DEFENSE = 0x200
    BASE_ATTACK = 0x400
    BASE_DEFENSE = 0x800
    REASON = 0x1000
    REASON_CARD = 0x2000
    EQUIP_CARD = 0x4000
    TARGET_CARD = 0x8000
    OVERLAY_CARD = 0x10000
    COUNTERS = 0x20000
    OWNER = 0x40000
    STATUS = 0x80000
    IS_PUBLIC = 0x100000
    LSCALE = 0x200000
    RSCALE = 0x400000
    LINK = 0x800000
    IS_HIDDEN = 0x1000000
    COVER = 0x2000000
    END = 0x80000000
    # the following are manually computed since position doesn't work like how it does in the main YgoPro core
    CONTROLLER = 0x10000000
    LOCATION = 0x20000000
    SEQUENCE = 0x40000000

PHASES = {
    1: _('draw phase'),
    2: _('standby phase'),
    4: _('main1 phase'),
    8: _('battle start phase'),
    0x10: _('battle step phase'),
    0x20: _('damage phase'),
    0x40: _('damage calculation phase'),
    0x80: _('battle phase'),
    0x100: _('main2 phase'),
    0x200: _('end phase'),
}


@unique
class REASON(IntFlag):
	DESTROY = 0x1
	RELEASE = 0x2
	TEMPORARY = 0x4
	MATERIAL = 0x8
	SUMMON = 0x10
	BATTLE = 0x20
	EFFECT = 0x40
	COST = 0x80
	ADJUST = 0x100
	LOST_TARGET = 0x200
	RULE = 0x400
	SPSUMMON = 0x800
	DISSUMMON = 0x1000
	FLIP = 0x2000
	DISCARD = 0x4000
	RDAMAGE = 0x8000
	RRECOVER = 0x10000
	RETURN = 0x20000
	FUSION = 0x40000
	SYNCHRO = 0x80000
	RITUAL = 0x100000
	XYZ = 0x200000
	REPLACE = 0x1000000
	DRAW = 0x2000000
	REDIRECT = 0x4000000
	LINK = 0x10000000
