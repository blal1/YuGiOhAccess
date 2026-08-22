from game.card.location_conversion import LocationConversion

def test_location_conversion_to_zone_key(mocker):
    # mock the client, so we can use it
    client = mocker.MagicMock()
    client.what_player_am_i = 0
    # create a LocationConversion object
    lc = LocationConversion(client, 0, 1, 2)
    # check the controller, location and sequence
    assert lc.controller == 0
    assert lc.location == 1
    assert lc.sequence == 2
    # check the to_zone_key method
    assert lc.to_zone_key() == "pd2"

def test_location_conversion_from_zone_key(mocker):
    # mock the client, so we can use it
    client = mocker.MagicMock()
    client.what_player_am_i = 0
    # create a LocationConversion object
    lc = LocationConversion.from_zone_key(client, "ph2")
    # check the controller, location and sequence
    assert lc.controller == 0
    assert lc.location == 2
    assert lc.sequence == 2

def test_location_conversion_from_card_location(mocker):
    # mock the client, so we can use it
    client = mocker.MagicMock()
    client.what_player_am_i = 0
    card = mocker.MagicMock()
    card.controller = 0
    card.location = 1
    card.sequence = 2
    card.position = 3
    # create a LocationConversion object
    lc = LocationConversion.from_card_location(client, card)
    # check the controller, location and sequence
    assert lc.controller == 0
    assert lc.location == 1
    assert lc.sequence == 2
