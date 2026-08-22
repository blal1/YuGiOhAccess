import re

from core.i18n import _
from game.card import card_constants

class LocationConversion:
    def __init__(self, client, controller, location, sequence):
        self.client = client
        self.controller = controller
        self.location = location
        self.sequence = sequence

    @staticmethod
    def from_card_location(client, card):
        return LocationConversion(client, card.controller, card.location, card.sequence)

    @staticmethod
    def from_zone_key(client, zone_key):
        # the text consist of first letters, followed by 1 or more digits
        # if the text starts with o, it's the opponent's zone
        # if the text starts with p, it's the player's zone
        # only exception is the extra monster zone, which is just "q0" or "q1"
        # the digits are the sequence number
        match = re.match(r"([op]?)([a-z]+)(\d+)", zone_key)
        if not match:
            if zone_key == "opf":
                return LocationConversion(client, 1 - client.what_player_am_i, card_constants.LOCATION.FIELD_ZONE, 0)
            elif zone_key == "pf":
                return LocationConversion(client, client.what_player_am_i, card_constants.LOCATION.FIELD_ZONE, 0)
            elif zone_key == "od":
                return LocationConversion(client, 1 - client.what_player_am_i, card_constants.LOCATION.DECK, 0)
            elif zone_key == "pd":
                return LocationConversion(client, client.what_player_am_i, card_constants.LOCATION.DECK, 0)
            else:
                return None
        opponent, location, sequence = match.groups()
        if opponent == "o":
            controller = 1 - client.what_player_am_i
        else:
            controller = client.what_player_am_i
        resolved_location = None
        if location == "q":
            resolved_location = card_constants.LOCATION.MONSTER_ZONE
            sequence = 5 if sequence == "0" else 6
            return LocationConversion(client, controller, resolved_location, sequence)
        if location == "m":
            resolved_location = card_constants.LOCATION.MONSTER_ZONE
        elif location == "s":
            resolved_location = card_constants.LOCATION.SPELL_AND_TRAP_ZONE
        elif location == "g":
            resolved_location = card_constants.LOCATION.GRAVE
        elif location == "r":
            resolved_location = card_constants.LOCATION.REMOVED
        elif location == "d":
            resolved_location = card_constants.LOCATION.DECK
        elif location == "h":
            resolved_location = card_constants.LOCATION.HAND
        elif location == "x":
            resolved_location = card_constants.LOCATION.EXTRA
        elif location == "f":
            resolved_location = card_constants.LOCATION.FIELD_ZONE
        elif location == "p":
            resolved_location = card_constants.LOCATION.PENDULUM_ZONE
        sequence = int(sequence)
        return LocationConversion(client, controller, resolved_location, sequence)
    

    def to_zone_key(self):
        if self.location == card_constants.LOCATION.MONSTER_ZONE:
            if self.sequence == 5:
                if self.controller == self.client.what_player_am_i:
                    return "q0"
                else:
                    return "q1"
            elif self.sequence == 6:
                if self.controller == self.client.what_player_am_i:
                    return "q1"
                else:
                    return "q0"
        if self.controller != self.client.what_player_am_i:
            controller = "o"
        else:
            controller = "p"
        location = None
        if self.location == card_constants.LOCATION.MONSTER_ZONE:
            location = "m"
        elif self.location == card_constants.LOCATION.SPELL_AND_TRAP_ZONE:
            location = "s"
        elif self.location == card_constants.LOCATION.GRAVE:
            location = "g"
        elif self.location == card_constants.LOCATION.REMOVED:
            location = "r"
        elif self.location == card_constants.LOCATION.DECK:
            location = "d"
        elif self.location == card_constants.LOCATION.HAND:
            location = "h"
        elif self.location == card_constants.LOCATION.EXTRA:
            location = "x"
        elif self.location == card_constants.LOCATION.FIELD_ZONE:
            location = "f"
        elif self.location == card_constants.LOCATION.PENDULUM_ZONE:
            location = "p"
        return f"{controller}{location}{self.sequence}"
    
    def to_human_readable(self):
        if self.controller == 1 - self.client.what_player_am_i:
            controller = _("Your opponents")
        else:
            controller = _("Your")
        location_string = self._convert_location_enum_value_to_string(self.location)
        return f"{controller} {location_string} {self.sequence+1}"
    
    def __eq__(self, other):
        # if other is a string, convert it to LocationConversion with from_zone_key
        if isinstance(other, str):
            return self == LocationConversion.from_zone_key(self.client, other)
        return self.controller == other.controller and self.location == other.location and self.sequence == other.sequence
    
    def __str__(self):
        return f"LocationConversion({self.controller}, {self.location}, {self.sequence}): {self.to_zone_key()}, {self.to_human_readable()}"

    def __repr__(self):
        return self.__str__()    

    def _convert_location_enum_value_to_string(self, location):
        if location == card_constants.LOCATION.MONSTER_ZONE:
            return _("monster zone")
        elif location == card_constants.LOCATION.SPELL_AND_TRAP_ZONE:
            return _("spell and trap zone")
        elif location == card_constants.LOCATION.GRAVE:
            return _("grave yard")
        elif location == card_constants.LOCATION.REMOVED:
            return _("banished")
        elif location == card_constants.LOCATION.DECK:
            return _("deck")
        elif location == card_constants.LOCATION.HAND:
            return _("hand")
        elif location == card_constants.LOCATION.EXTRA:
            return _("extra deck")
        elif location == card_constants.LOCATION.FIELD_ZONE:
            return _("field zone")
        elif location == card_constants.LOCATION.PENDULUM_ZONE:
            return _("pendulum zone")
        else:
            return _("unknown location")

