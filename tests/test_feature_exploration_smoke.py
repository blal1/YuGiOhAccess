import importlib
import pkgutil
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_all_ui_and_duel_message_modules_import_without_starting_client():
    import ui
    import ui.duel_messages

    skipped = {"ui.app"}
    failures = []
    for package in (ui, ui.duel_messages):
        for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
            if module_info.name in skipped or module_info.ispkg:
                continue
            try:
                importlib.import_module(module_info.name)
            except Exception as exc:
                failures.append(f"{module_info.name}: {exc!r}")

    assert failures == []


def test_registered_packet_and_duel_handlers_cover_runtime_paths():
    from core import utils

    import ui.room_ui  # noqa: F401
    import ui.duel_messages.announce_attrib  # noqa: F401
    import ui.duel_messages.announce_card  # noqa: F401
    import ui.duel_messages.announce_number  # noqa: F401
    import ui.duel_messages.announce_race  # noqa: F401
    import ui.duel_messages.attack  # noqa: F401
    import ui.duel_messages.chaining  # noqa: F401
    import ui.duel_messages.confirm_cards  # noqa: F401
    import ui.duel_messages.draw  # noqa: F401
    import ui.duel_messages.idle  # noqa: F401
    import ui.duel_messages.move  # noqa: F401
    import ui.duel_messages.select_card  # noqa: F401
    import ui.duel_messages.select_chain  # noqa: F401
    import ui.duel_messages.select_option  # noqa: F401
    import ui.duel_messages.select_position  # noqa: F401
    import ui.duel_messages.select_yes_no  # noqa: F401
    import ui.duel_messages.start  # noqa: F401
    import ui.duel_messages.update_data  # noqa: F401
    import ui.duel_messages.win  # noqa: F401
    from game.edo import structs

    assert structs.ServerIdType.CREATE_GAME in utils.packet_handlers
    assert structs.ServerIdType.JOIN_GAME in utils.packet_handlers
    assert structs.ServerIdType.PLAYER_ENTER in utils.packet_handlers
    assert structs.ServerIdType.PLAYER_CHANGE in utils.packet_handlers
    assert structs.ServerIdType.TYPE_CHANGE in utils.packet_handlers
    assert structs.ServerIdType.GAME_MSG in utils.packet_handlers
    assert len(utils.duel_message_handlers) >= 30


def test_core_interface_menus_are_constructible_without_client_launch(mocker):
    from tests.test_ui_flows_more import FakeMenu
    from ui import card_search_ui, deck_editor_ui, main_ui, replay_ui, room_ui, server_ui

    for module_name in (
        "ui.main_ui",
        "ui.server_ui",
        "ui.room_ui",
        "ui.deck_editor_ui",
        "ui.card_search_ui",
        "ui.replay_ui",
    ):
        mocker.patch(f"{module_name}.VerticalMenu", FakeMenu)

    mocker.patch("ui.main_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    mocker.patch("ui.room_ui.utils.get_discord_presence_manager", return_value=MagicMock())
    mocker.patch("ui.main_ui.wx.GetTopLevelWindows", return_value=[MagicMock()])
    mocker.patch("ui.room_ui.DynamicVerticalMenu", FakeMenu)
    mocker.patch("ui.server_ui.WaitUI")
    mocker.patch("ui.server_ui.get_servers", return_value=[])
    mocker.patch("ui.card_search_ui.CardSearchResultsUI", side_effect=lambda return_to, rows: ("card-results", rows))
    mocker.patch("ui.card_search_ui._search_cards", return_value=[(1, "Alpha")])
    mocker.patch("ui.card_search_ui._format_card_summary", return_value="monster")
    mocker.patch("ui.replay_ui.get_replay_dir", return_value=mocker.MagicMock())

    replay_dir = replay_ui.get_replay_dir.return_value
    replay_dir.mkdir.return_value = None
    replay_dir.iterdir.return_value = []

    main_ui.variables.DEV_OPTIONS = SimpleNamespace(server=None)
    main_ui.variables.IS_FROZEN = False
    main_ui.variables.APP_VERSION = "1.0"
    main_ui.variables.config = MagicMock()
    main_ui.variables.config.get.side_effect = lambda key, default=None: {
        "nickname": "Tester",
        "ui_language": "en",
        "language": "english",
        "enable_hints": True,
        "screenreader_output_only_on_application_focus": True,
        "helper_zones": True,
        "rock_paper_scissors_bot_behavior": "random",
        "enable_bot_chat": True,
    }.get(key, default)
    main_ui.variables.LANGUAGE_HANDLER = MagicMock(languages={"english": {}})

    assert any(item[0] == "Card Search" for item in main_ui.main_menu_view.__wrapped__().items)
    assert any(item[0] == "New Deck" for item in deck_editor_ui.deck_editor_main_menu.__wrapped__(main_ui.main_menu_view).items)
    assert any(item[0] == "Search by name" for item in card_search_ui.card_search_menu.__wrapped__(main_ui.main_menu_view).items)
    assert any(item[0] == "Back" for item in replay_ui.replay_viewer_menu.__wrapped__(main_ui.main_menu_view).items)
    assert any(item[0] == "Back" for item in server_ui.server_selection_menu.__wrapped__().items)

    room = SimpleNamespace(
        roomid=1,
        needpass=False,
        roomnotes="",
        best_of=1,
        users=[],
        team1="1",
        team2="1",
        banlist_hash=0,
    )
    client = MagicMock()
    client.room = room
    client.room_id = 1
    client.memory = SimpleNamespace(is_host=False, is_observer=False, users_info=[])
    room_menu = room_ui.display_room_menu.__wrapped__(client)
    assert any(item[0] == "Select/import Deck" for item in room_menu.items)
