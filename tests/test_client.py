import io
import struct
from game.client import Client
from game.card import card_constants
from ui.duel_field import Zone, ZONE_KEYS

def test_client(mocker):
    server = mocker.MagicMock()
    client = Client(server)
    assert client.what_player_am_i == -1
    
def test_read_uint8(mocker):
    server = mocker.MagicMock()
    client = Client(server)
    # make a list, of the values between 0 and 10
    values = list(range(10))
    # make a buffer that contains the values
    buffer = _compose_bytestring(values, "B")
    # then read them
    buffer = io.BytesIO(buffer)
    for i in range(10):
        assert client.read_u8(buffer) == i

def test_read_uint32(mocker):
    server = mocker.MagicMock()
    client = Client(server)
    # make a list, of the values between 0 and 10
    values = list(range(10))
    # make a buffer that contains the values
    buffer = _compose_bytestring(values, "I")
    # then read them
    buffer = io.BytesIO(buffer)
    for i in range(10):
        assert client.read_u32(buffer) == i

def test_read_uint64(mocker):
    server = mocker.MagicMock()
    client = Client(server)
    # make a list, of the values between 0 and 10
    values = list(range(10))
    # make a buffer that contains the values
    buffer = _compose_bytestring(values, "Q")
    # then read them
    buffer = io.BytesIO(buffer)
    for i in range(10):
        assert client.read_u64(buffer) == i

def test_read_location_normal(mocker):
    server = mocker.MagicMock()
    client = Client(server)
    buf = b""
    buf += _compose_bytestring([0, card_constants.LOCATION.HAND.value], "B")
    # then an uint 32
    buf += struct.pack("I", 4)
    # then another uint 32
    buf += struct.pack("I", 8)
    # convert the buffer to a BytesIO object
    buffer = io.BytesIO(buf)
    # read the location
    controller, location, sequence, position = client.read_location(buffer)
    assert controller == 0
    assert location == 2
    assert sequence == 4
    assert position == 8

def test_read_location_without_position(mocker):
    # will happen if the card/location read is an overlay unit
    server = mocker.MagicMock()
    client = Client(server)
    buf = b""
    # so the location (second number is MONSTER_ZONE and OVERLAY)
    buf += _compose_bytestring([0, card_constants.LOCATION.OVERLAY.value], "B")
    # then an uint 32
    buf += struct.pack("I", 4)
    print(buf)
    # convert the buffer to a BytesIO object
    buffer = io.BytesIO(buf)
    # read the location
    controller, location, sequence, position = client.read_location(buffer)
    assert controller == 0
    assert location == card_constants.LOCATION.OVERLAY.value
    assert sequence == 4
    assert position == 0

def _compose_bytestring(values, struct_pack_format):
    buf = b""
    for value in values:
        buf += struct.pack(struct_pack_format, value)
    return buf

def test_get_card_invalid_zone(mocker):
    server = mocker.MagicMock()
    duel_field = mocker.MagicMock()
    duel_field.zones = {}
    client = Client(server)
    client.set_duel_field(duel_field)
    assert not client.get_card(0, 1, 1, max_retries=2)

def test_get_card_valid_zone(mocker):
    server = mocker.MagicMock()
    duel_field = mocker.MagicMock()
    zone_key = ZONE_KEYS.PLAYER_HAND.format(4)
    zone = Zone(zone_key, "random card")
    duel_field.zones = {zone_key: zone}
    client = Client(server)
    client.set_duel_field(duel_field)
    client.what_player_am_i = 0
    assert client.get_card(0, 2, 4, max_retries=2) == "random card"