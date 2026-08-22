def cards_match(zone_card, playable_card):
    if zone_card is playable_card:
        return True
    if zone_card is None or playable_card is None:
        return False
    for attr in ("controller", "location", "sequence"):
        if getattr(zone_card, attr, None) != getattr(playable_card, attr, None):
            return False
    zone_code = getattr(zone_card, "code", 0)
    playable_code = getattr(playable_card, "code", 0)
    if zone_code and playable_code and zone_code != playable_code:
        return False
    return True


def matching_cards(zone_card, playable_cards):
    return [card for card in playable_cards if cards_match(zone_card, card)]


def first_matching_index(playable_cards, card, addition=0):
    matching_indexes = [index for index, playable_card in enumerate(playable_cards) if cards_match(card, playable_card)]
    target_position = int(addition)
    if target_position < 0 or target_position >= len(matching_indexes):
        raise ValueError("Playable card action index is out of range")
    return matching_indexes[target_position]


def playable_zone_keys(zones, playable_cards, card_type):
    if not playable_cards:
        return []
    zone_keys = []
    for zone_key, zone in zones.items():
        zone_card = getattr(zone, "card", None)
        if not isinstance(zone_card, card_type):
            continue
        if matching_cards(zone_card, playable_cards):
            zone_keys.append(zone_key)
    return zone_keys
