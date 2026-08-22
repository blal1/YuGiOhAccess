import pytest


@pytest.fixture(autouse=True)
def prevent_client_thread_hang(mocker):
    """Prevent Client from starting its busy-wait packet_listener thread during tests."""
    import game.client

    if not hasattr(game.client, "ORIGINAL_PACKET_LISTENER"):
        game.client.ORIGINAL_PACKET_LISTENER = game.client.Client.packet_listener
    mocker.patch("game.client.Client.packet_listener")
