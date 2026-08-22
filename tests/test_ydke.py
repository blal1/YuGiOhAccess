import json
from pathlib import Path

from game.card import ydke

ydke_deck_string = "ydke://1l9hA9ZfYQOlm8MBISD0BIUG5QGFBuUBhQblAaCUBAITR2UAihkQBYoZEAWKGRAFNTP8ADUz/AD4NdICiTh0BCn2rADeMuoF4YmwA5G+ZAWsseoF3Jh8ANoj6wP9HWIElrpzAdILiwWlm8MByhq/AfG+mwHoVOkAoy8IAo6sXAGcb/MBnG/zAZxv8wGlm8MB+jitBTUz/AD+CoAEulWoAhNHZQDzhdIF84XSBRmiigG4gQkDxanaBGzVlAANaDYF84XSBdfjOQRWE9UBXWneAl1p3gJdad4CSIizAH6JQwM=!!UveKA1L3igNS94oD66qLBdHCeAXRwngF0cJ4Ba+6gwVsWNMDjyVbBB0t6AIdLegCHS3oAiaQQgMmkEID"
deck_file = Path(__file__).parent / "data/deck.json"
json_deck_data = json.loads(deck_file.read_text(encoding="utf-8"))

def test_deck_from_ydke():
    deck = ydke.Deck.from_ydke(ydke_deck_string)
    assert deck.cards == list(json_deck_data["main"].values())
    assert deck.side == list(json_deck_data["side"].values())

def test_deck_to_ydke():
    deck = ydke.Deck(list(json_deck_data["main"].values()), list(json_deck_data["side"].values()))
    assert deck.to_ydke() == ydke_deck_string

def test_deck_from_json():
    deck = ydke.Deck.from_json(json.dumps(json_deck_data))
    print(type(deck.cards))
    assert deck.cards == list(json_deck_data["main"].values())
    assert deck.side == list(json_deck_data["side"].values())

def test_deck_to_json():
    deck = ydke.Deck(list(json_deck_data["main"].values()), list(json_deck_data["side"].values()))
    assert json.loads(deck.to_json()) == json_deck_data

def test_deck_from_json_to_ydke():
    deck = ydke.Deck.from_json(json.dumps(json_deck_data))
    assert deck.to_ydke() == ydke_deck_string

def test_deck_from_ydke_to_json():
    deck = ydke.Deck.from_ydke(ydke_deck_string)
    assert json.loads(deck.to_json()) == json_deck_data