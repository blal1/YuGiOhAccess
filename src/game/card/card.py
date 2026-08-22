from core import variables
from core import exceptions

from game.card import card_constants

class Card:
    def __init__(self, code):
        if code == 0: # code that the clien't aren't allowed to know about, like opponent facedowns.
            self.code = 0
            self.alias = 0
            self.setcode = 0
            self.type = 0
            self.level = 0
            self.lscale = 0
            self.rscale = 0
            self.attack = 0
            self.defense = 0
            self.name = ''
            self.desc = ''
            self.strings = []
            return
        row = variables.LANGUAGE_HANDLER.primary_database.execute('select * from datas where id=?', (code,)).fetchone()
        if row is None:
            raise exceptions.CardNotFoundException("Card %d not found" % code)
        self.data = 0 # additional data fetched in certain cases (see Duel.read_cardlist)
        self.param = 0 # additional data fetched in certain cases (see select_sum)
        self.code = code
        self.alias = row['alias']
        self.setcode = row['setcode']
        self.type = card_constants.TYPE(row['type'])
        self.level = row['level'] & 0xff
        self.lscale = (row['level'] >> 24) & 0xff
        self.rscale = (row['level'] >> 16) & 0xff
        self.attack = row['atk']
        self.defense = row['def']
        self.race = row['race']
        self.attribute = row['attribute']
        self.category = row['category']
        row = variables.LANGUAGE_HANDLER.primary_database.execute('select * from texts where id = ?', (self.code, )).fetchone()
        self.name = row[1]
        self.desc = row[2]
        self.strings = []
        for i in range(3, len(row), 1):
            self.strings.append(row[i])

    def set_location_and_position_info(self, controller, location, sequence, position):
        self.controller = controller
        self.location = location
        self.sequence = sequence
        self.position = position

    def set_location_and_position_by_unpacking(self, location):
        self.controller = location & 0xff
        self.location = card_constants.LOCATION((location >> 8) & 0xff)
        self.sequence = (location >> 16) & 0xff
        self.position = card_constants.POSITION((location >> 24) & 0xff)


    def get_name(self):
        get_translation = getattr(variables.LANGUAGE_HANDLER, "get_card_translation", None)
        if get_translation:
            translation = get_translation(self.code)
            if isinstance(translation, dict) and translation.get("name"):
                return translation["name"]
        name = self.name
        row = variables.LANGUAGE_HANDLER.primary_database.execute('select name from texts where id=?', (self.code,)).fetchone()
        if row:
            return row[0]
        return name

    def get_description(self):
        get_translation = getattr(variables.LANGUAGE_HANDLER, "get_card_translation", None)
        if get_translation:
            translation = get_translation(self.code)
            if isinstance(translation, dict) and translation.get("desc"):
                return translation["desc"]
        desc = self.desc
        row = variables.LANGUAGE_HANDLER.primary_database.execute('select desc from texts where id=?', (self.code,)).fetchone()
        if row:    
            return row[0]
        return desc


    def __str__(self):
        lst = []
        types = []
        for i in range(len(card_constants.TYPE)):
            if self.type & (1 << i):
                types.append(variables.LANGUAGE_HANDLER.strings['system'][1050+i])
        for i in range(card_constants.AMOUNT_ATTRIBUTES):
            if self.attribute & (1 << i):
                types.append(variables.LANGUAGE_HANDLER.strings['system'][card_constants.ATTRIBUTES_OFFSET+i])
        for i in range(card_constants.AMOUNT_RACES):
            if self.race & (1 << i):
                types.append(variables.LANGUAGE_HANDLER.strings['system'][card_constants.RACES_OFFSET+i])
        lst.append("%s (%s)" % (self.get_name(), ", ".join(types)))
        set_names = self.get_set_names()
        if set_names:
            lst.append(variables.LANGUAGE_HANDLER._("Archetype: %s") % set_names)
        if self.type & card_constants.TYPE.MONSTER:
            if self.type & card_constants.TYPE.LINK:
                lst.append(variables.LANGUAGE_HANDLER._("Attack: %d Link rating: %d")%(self.attack, self.level))
            elif self.type & card_constants.TYPE.XYZ:
                lst.append(variables.LANGUAGE_HANDLER._("Attack: %d Defense: %d Rank: %d") % (self.attack, self.defense, self.level))
            else:
                lst.append(variables.LANGUAGE_HANDLER._("Attack: %d Defense: %d Level: %d") % (self.attack, self.defense, self.level))
        if self.type & card_constants.TYPE.PENDULUM:
            lst.append(variables.LANGUAGE_HANDLER._("Pendulum scale: %d/%d") % (self.lscale, self.rscale))
        elif self.type & card_constants.TYPE.LINK:
            lst.append(variables.LANGUAGE_HANDLER._("Link Markers: %s")%(self.get_link_markers()))
        lst.append(self.get_description())
        try:
            if self.type & card_constants.TYPE.XYZ and self.location == card_constants.LOCATION.MONSTER_ZONE:
                if len(self.xyz_materials) > 0:
                    lst.append(variables.LANGUAGE_HANDLER._("attached xyz materials:"))
                    for i in range(len(self.xyz_materials)):
                        lst.append(str(i+1)+": "+self.xyz_materials[i].get_name())
                else:
                    lst.append(variables.LANGUAGE_HANDLER._("no xyz materials attached"))
        except AttributeError:
            pass
        return "\n".join(lst)

    def __repr__(self):
        return self.get_name()

    @property
    def extra(self):
        return bool(self.type & card_constants.TYPE.EXTRA)

    def get_link_markers(self):
        lst = []
        for m in card_constants.LINK_MARKERS.keys():
            if self.defense & m:
                lst.append(variables.LANGUAGE_HANDLER._(card_constants.LINK_MARKERS[m]))
        return ', '.join(lst)

    def get_set_names(self):
        set_names = variables.LANGUAGE_HANDLER.strings.get('setname', {})
        setcode_value = getattr(self, 'setcode', 0)
        if not setcode_value:
            return ''
        names = []
        for i in range(4):
            setcode = (setcode_value >> (i * 16)) & 0xffff
            if not setcode:
                continue
            for key in (setcode & 0xff, setcode):
                name = set_names.get(key)
                if name and name not in names:
                    names.append(name)
        return ', '.join(names)

    def __eq__(self, other):
        if not isinstance(other, Card):
            return False
        return self.code == other.code and self.location == other.location and self.sequence == other.sequence and self.controller == other.controller and self.position == other.position
    
    def __contains__(self, item):
        return self.code == item.code and self.location == item.location and self.sequence == item.sequence and self.controller == item.controller and self.position == item.position

    def get_effect_description(self, i, existing=False):
        s = ''
        e = False
        if i > 10000:
            code = i >> 4
        else:
            code = self.code
        lstr = self.get_strings(code)
        try:
            if i == 0 or lstr[i-code*16].strip() == '':
                s = variables.LANGUAGE_HANDLER._("Activate this card.")
            else:
                s = lstr[i-code*16].strip()
                e = True
        except IndexError:
            s = variables.LANGUAGE_HANDLER.strings['system'].get(i, '')
            if s != '':
                e = True
        if existing and not e:
            s = ''
        return s

    def get_position(self):
        if self.position == card_constants.POSITION.FACE_UP_ATTACK:
            return variables.LANGUAGE_HANDLER._("face-up attack")
        elif self.position == card_constants.POSITION.FACE_DOWN_ATTACK:
            return variables.LANGUAGE_HANDLER._("face-down attack")
        elif self.position == card_constants.POSITION.FACE_UP_DEFENSE:
            if self.location & card_constants.LOCATION.EXTRA:
                return variables.LANGUAGE_HANDLER._("face-up")
            return variables.LANGUAGE_HANDLER._("face-up defense")
        elif self.position == card_constants.POSITION.FACE_UP:
            return variables.LANGUAGE_HANDLER._("face-up")
        elif self.position == card_constants.POSITION.FACE_DOWN_DEFENSE:
            if self.location & card_constants.LOCATION.EXTRA:
                return variables.LANGUAGE_HANDLER._("face down")
            return variables.LANGUAGE_HANDLER._("face-down defense")
        elif self.position == card_constants.POSITION.FACE_DOWN:
            return variables.LANGUAGE_HANDLER._("face down")

    def get_strings(self, code=None):
        row = variables.LANGUAGE_HANDLER.cdb.execute('select * from texts where id = ?', (code or self.code, )).fetchone()
        if not row:
            return self.strings
        strings = []
        for i in range(3, len(row), 1):
            strings.append(row[i])
        return strings
