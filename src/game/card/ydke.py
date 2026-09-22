import json
import base64
import binascii
import struct

from game.card.card import Card

class URLParseError(Exception):
    pass

class Deck:
    def __init__(self, cards, side=[], loaded_from=None):
        self.cards = list(cards)
        self.side = list(side)
        self.loaded_from = loaded_from

    @staticmethod
    def from_ydke(url):
        if url.startswith('ydke://'):
            s = url[7:]
        else:
            raise URLParseError
        components = s.split('!')
        try:
            components = [base64.decodebytes(c.encode('ascii')) for c in components]
        except binascii.Error:
            raise URLParseError
        if len(components) < 2:
            raise URLParseError
        try:
            components = [struct.unpack('<%di' % (len(c) / 4), c) for c in components]
        except struct.error:
            raise URLParseError
        cards = components[0] + components[1]
        side = []
        if len(components) > 2:
            side = components[2]
        return Deck(cards, side, "ydke")


    def to_ydke(self):
        cards = struct.pack('<%di' % len(self.cards), *self.cards)
        cards = base64.standard_b64encode(cards).decode('ascii')
        side = struct.pack('<%di' % len(self.side), *self.side)
        side = base64.standard_b64encode(side).decode('ascii')
        return 'ydke://%s!!%s' % (cards, side)

    @staticmethod
    def from_json(data):
        try:
            deck_json = json.loads(data)
            cards = deck_json["main"].values()
            side = deck_json["side"].values()
            return Deck(cards, side, "json")
        except json.JSONDecodeError:
            raise URLParseError
        
    def to_json(self):
        return json.dumps({"main": {i: card for i, card in enumerate(self.cards)}, "side": {i: card for i, card in enumerate(self.side)}}, indent=4)
    
    @staticmethod
    def from_windbot_format(data):
        main_deck = []
        extra_deck = []
        side_deck = []
        fill_up_main_deck = False
        fill_up_extra_deck = False
        fill_up_side_deck = False
        # split the data in lines.
        lines = data.split("\n")
        for line in lines:
            line = line.strip()
            # if the line is empty, ignore it
            if not line:
                continue
            # if the line starts with #main, start filling up the main deck
            if line.startswith("#main"):
                fill_up_main_deck = True
                fill_up_extra_deck = False
                fill_up_side_deck = False
                continue
            # if the deck starts with #extra, start filling up the extra deck
            if line.startswith("#extra"):
                fill_up_main_deck = False
                fill_up_extra_deck = True
                fill_up_side_deck = False
                continue
            # if the deck starts with !side, start filling up the side deck
            if line.startswith("!side"):
                fill_up_main_deck = False
                fill_up_extra_deck = False
                fill_up_side_deck = True
                continue
            # if the line sotherwise starts with # ignore it
            if line.startswith("#"):
                continue
            # every line now should be a card id
            try:
                card_id = int(line)
            except ValueError:
                raise
            if fill_up_main_deck:
                main_deck.append(card_id)
            elif fill_up_extra_deck:
                extra_deck.append(card_id)
            elif fill_up_side_deck:
                side_deck.append(card_id)
        # ``cards`` holds the main and extra deck together, the way every other
        # constructor here fills it and the way to_windbot_format reads it back
        # out. Passing the main deck alone dropped the extra deck on the floor.
        return Deck(main_deck + extra_deck, side_deck, "windbot")
    
    def to_windbot_format(self):
        deck_string = ""
        main_deck = []
        extra_deck = []
        for card_id in self.cards:
            card = Card(card_id)
            if card.extra:
                extra_deck.append(card_id)
            else:
                main_deck.append(card_id)
        deck_string += "#main\n"
        for card_id in main_deck:
            deck_string += f"{card_id}\n"
        deck_string += "#extra\n"
        for card_id in extra_deck:
            deck_string += f"{card_id}\n"
        deck_string += "!side\n"
        for card_id in self.side:
            deck_string += f"{card_id}\n"
        return deck_string

    def __str__(self):
        return f"Deck(Main+extra deck: {len(self.cards)}, Side deck: {len(self.side)}, loaded from {self.loaded_from})"
