import pytest


@pytest.fixture(autouse=True)
def prevent_client_thread_hang(mocker):
    """Prevent Client from starting its busy-wait packet_listener thread during tests."""
    import game.client

    if not hasattr(game.client, "ORIGINAL_PACKET_LISTENER"):
        game.client.ORIGINAL_PACKET_LISTENER = game.client.Client.packet_listener
    mocker.patch("game.client.Client.packet_listener")


@pytest.fixture
def write_catalogue():
    """Write a real compiled .mo file.

    A handful of bytes is not a catalogue. Now that a language is only offered
    when its catalogue loads and holds a translation, tests that want a
    language to be offered have to produce a genuine one.
    """
    from babel.messages.catalog import Catalog
    from babel.messages.mofile import write_mo

    def _write(mo_path, translations=None, locale=None):
        # `translations or {...}` would turn an explicitly empty catalogue --
        # the whole point of some of these tests -- back into a full one.
        if translations is None:
            translations = {"Hello": "Bonjour"}
        catalogue = Catalog(locale=locale)
        for message, translation in translations.items():
            catalogue.add(message, translation)
        mo_path.parent.mkdir(parents=True, exist_ok=True)
        with mo_path.open("wb") as handle:
            write_mo(handle, catalogue)
        return mo_path

    return _write


@pytest.fixture(autouse=True)
def restore_handler_registries():
    """Keep synthetic handlers from leaking between tests.

    Several tests register handlers on made up ids to exercise the error paths.
    Those used to stay in the global registry for the rest of the session, which
    makes any assertion about the registered id set order dependent.
    """
    from core import utils

    duel_snapshot = dict(utils.duel_message_handlers)
    packet_snapshot = dict(utils.packet_handlers)
    yield
    utils.duel_message_handlers.clear()
    utils.duel_message_handlers.update(duel_snapshot)
    utils.packet_handlers.clear()
    utils.packet_handlers.update(packet_snapshot)
