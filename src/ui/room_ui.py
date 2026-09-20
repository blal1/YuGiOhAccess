import json
import logging
from pathlib import Path
import random

import wx
import requests
from core import utils
from core import variables
from core.i18n import _

from game.edo import banlists, structs, structs_utils
from game.card.card import Card

from game.card import ydke
from ui.base_ui import VerticalMenu, DynamicVerticalMenu, StatusMessage
from ui import server_ui
from ui import match_ui

logger = logging.getLogger(__name__)

@utils.packet_handler(structs.ServerIdType.CREATE_GAME)
def handle_create_game(client, packet_data, packet_length):
    message = structs.StocCreateGame.from_buffer_copy(packet_data)
    try:
        utils.output(_("Created room with ID {id} and password {password}").format(id=message.id, password=client.memory.room_password))
    except AttributeError:
        utils.output(_("Created room with ID {id}").format(id=message.id))

@utils.packet_handler(structs.ServerIdType.JOIN_GAME)
def handle_join_game(client, packet_data, packet_length):
    utils.output(_("Joined game"))
    client.memory.users_info = []
    if variables.DEV_OPTIONS.deck:
        path = Path(variables.DECK_DIR / f"{variables.DEV_OPTIONS.deck}.json")
        if path.exists():
            handle_deck_menu_select_deck(client, path)
        else:
            utils.output(_("Deck {name} not found").format(name=variables.DEV_OPTIONS.deck))
    if variables.DEV_OPTIONS.bot:
        if variables.DEV_OPTIONS.botdeck:
            # capitalize the first letter of the bot deck
            deck = variables.DEV_OPTIONS.botdeck[0].upper() + variables.DEV_OPTIONS.botdeck[1:]
            add_bot_to_room(client, deck)
        else:
            add_bot_to_room(client)
    return display_room_menu(client)

@utils.packet_handler(structs.ServerIdType.PLAYER_ENTER)
def handle_player_enter(client, packet_data, packet_length):
    try:
        player_name, position = _parse_player_enter_packet(packet_data)
    except ValueError:
        logger.warning("Ignoring malformed PLAYER_ENTER packet with length %s", packet_length)
        return
    client.memory.users_info.append({"name": player_name, "ready": False, "host": False, "position": position})
    utils.output(_("{player} entered the room at position {pos}").format(player=player_name, pos=position))


def _parse_player_enter_packet(packet_data):
    if len(packet_data) < 41:
        raise ValueError(f"PLAYER_ENTER packet too short: {len(packet_data)} bytes")
    player_name = packet_data[:40].decode("utf-16-le", errors="replace").rstrip("\x00")
    return player_name, packet_data[40]

@utils.packet_handler(structs.ServerIdType.PLAYER_CHANGE)
def handle_player_change(client, packet_data, packet_length):
    result = structs.StocPlayerChange.from_buffer_copy(packet_data)
    team = result.position()
    is_ready = result.is_ready()
    is_spectator = result.status & 0xf == structs.StocChangeType.SPECTATE
    for user in client.memory.users_info:
        if user["position"] == team:
            user["ready"] = is_ready
            user["spectator"] = is_spectator
    if is_spectator:
        status = _("spectating")
    else:
        status = _("ready") if is_ready else _("not ready")
    utils.output(_("Team {team} is {status}").format(team=team, status=status))

@utils.packet_handler(structs.ServerIdType.TYPE_CHANGE)
def handle_type_change(client, packet_data, packet_length):
    result = structs.StocTypeChange.from_buffer_copy(packet_data)
    team = result.position()
    is_host = result.is_host()
    if team < 7:
        client.what_player_am_i = team
    for user in client.memory.users_info:
        if user["position"] == team:
            user["host"] = is_host
    utils.output(_("Team {team} is {status}").format(team=team, status=_("host") if is_host else _("not host")))

@utils.ui_function
def display_room_menu(client):
    utils.get_ui_stack().clear_ui_stack()
    logger.debug("Displaying room menu")
    room = client.room
    if not room:
        return _room_unavailable_menu(client)
    room_menu = DynamicVerticalMenu(_("Room Menu"))
    users = getattr(room, "users", []) or []
    basic_room_information = _("Room ID: {id}.").format(id=getattr(room, "roomid", getattr(client, "room_id", _("unknown")))) + "\n"
    if getattr(room, "needpass", False):
        basic_room_information += _("Password: {password}.").format(password=getattr(client.memory, "room_password", "")) + "\n"
    else:
        basic_room_information += _("Password: None.") + "\n"
    roomnotes = getattr(room, "roomnotes", "")
    if roomnotes:
        basic_room_information += f"{roomnotes}.\n"
    banlist = _get_room_banlist(room)
    banlist_name = getattr(banlist, "name", None) or _("Unknown banlist")
    basic_room_information += _("Banlist: {name}.").format(name=banlist_name) + "\n"
    team1_count, team2_count = _room_team_counts(room)
    capacity = team1_count + team2_count
    if capacity > 2:
        basic_room_information += _("Duel type: Tag duel {team1} vs {team2}.").format(team1=team1_count, team2=team2_count) + "\n"
    else:
        basic_room_information += _("Duel type: 1 vs 1.") + "\n"
    basic_room_information += _("Format: {format}.").format(
        format=_("Best of 3 match") if getattr(room, "best_of", 1) == 3 else _("Single duel")
    ) + "\n"
    basic_room_information += _("Players: {current}/{capacity}.").format(current=len(users), capacity=capacity) + "\n"
    if getattr(room, "best_of", 1) == 3:
        basic_room_information += _("Side decking is available between games.") + "\n"
        basic_room_information += match_ui.score_text(client) + "\n"
    room_menu.append_item(str(basic_room_information))
    # show the players in the room.
    room_menu.append_item(str(resolve_players(client)))
    #participants.Bind(wx.EVT_SET_FOCUS, lambda e: utils.output(resolve_players(client)))
    if client.memory.is_host and capacity == 2 and len(users) < capacity:
        room_menu.append_item(_("Add a bot opponent"), lambda: handle_add_bot_as_opponent(client))
    if getattr(client.memory, "is_observer", False):
        room_menu.append_item(_("Spectating this room"), None)
    else:
        room_menu.append_item(_("Select/import Deck"), lambda: handle_room_menu_select_deck(client))
        room_menu.append_item(_("Check deck against room banlist"), lambda: handle_room_menu_check_deck_against_banlist(client))
        if client.memory.is_host:
            room_menu.append_item(_("Start"), lambda: handle_room_menu_ready_or_start(client))
        elif getattr(client.memory, "is_ready", False):
            room_menu.append_item(_("Not ready"), lambda: handle_room_menu_not_ready(client))
        else:
            room_menu.append_item(_("Ready"), lambda: handle_room_menu_ready_or_start(client))
    if client.memory.is_host and len(users) > 1:
        room_menu.append_item(_("Remove a player"), lambda: handle_room_menu_kick(client))
    room_menu.append_item(_("Back"), lambda: handle_me_disconnect(client))
    utils.get_discord_presence_manager().update_presence(
        state=_("In a room"),
        details=_("Waiting for an opponent"),
        party_size=[len(users), capacity],
    )
    return room_menu


def _room_unavailable_menu(client):
    room_menu = DynamicVerticalMenu(_("Room unavailable"))
    room_menu.append_item(_("Room information could not be loaded."))
    room_menu.append_item(_("Back"), lambda: handle_me_disconnect(client))
    return room_menu


def _get_room_banlist(room):
    banlist_manager = banlists.BanlistManager()
    banlist = banlist_manager.get_banlist_by_hash(_room_banlist_hash(room))
    if banlist:
        return banlist
    fallback = banlists.Banlist()
    fallback.name = _("Unknown banlist")
    return fallback


def _room_capacity(room):
    team1_count, team2_count = _room_team_counts(room)
    return team1_count + team2_count


def _room_banlist_hash(room):
    for attr in ("banlist_hash", "lflist"):
        try:
            return int(getattr(room, attr))
        except (AttributeError, TypeError, ValueError):
            pass
    try:
        return int(room.host_info["banlist_hash"])
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    try:
        return int(room.host_info["lflist"])
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    return 0


def _room_team_counts(room):
    try:
        team1 = int(room.team1)
        team2 = int(room.team2)
        if team1 > 0 and team2 > 0:
            return team1, team2
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        team1 = int(room.host_info.t0_count)
        team2 = int(room.host_info.t1_count)
        if team1 > 0 and team2 > 0:
            return team1, team2
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        team1 = int(room.host_info["t0_count"])
        team2 = int(room.host_info["t1_count"])
        if team1 > 0 and team2 > 0:
            return team1, team2
    except (AttributeError, KeyError, TypeError, ValueError):
        pass
    return 1, 1


def _team_label_for_position(room, position):
    try:
        position = int(position)
    except (TypeError, ValueError):
        return _("Team {position}").format(position=position)
    team1_count, team2_count = _room_team_counts(room)
    if position < team1_count:
        return _("Team 1 slot {slot}").format(slot=position + 1)
    if position < team1_count + team2_count:
        return _("Team 2 slot {slot}").format(slot=position - team1_count + 1)
    return _("Spectator")

def resolve_players(client):
    users = getattr(client.room, "users", []) or []
    names = [team["name"] for team in users]
    new_memory = []
    for team in client.memory.users_info:
        if team["name"] not in names:
            continue
        team["position"] = users[names.index(team["name"])]["pos"]
        new_memory.append(team)
    client.memory.users_info = new_memory
    player_and_position = ""
    for team in client.memory.users_info:
        if team.get("spectator"):
            player_and_position += _("Spectator - {name} ").format(name=team["name"])
        else:
            player_and_position += _("{team} - {name} ").format(team=_team_label_for_position(client.room, team["position"]), name=team["name"])
        if team["host"]:
            player_and_position += _("(host) ")
        player_and_position += _("is ready") + "\n" if team["ready"] else _("is not ready") + "\n"
    return player_and_position

def handle_room_menu_ready_or_start(client):
    if not hasattr(client.memory, "deck"):
        sm = StatusMessage(_("You must select a deck first"), lambda: display_room_menu(client))
        sm.show()
        return
    client.send(structs.ClientIdType.READY)
    client.memory.is_ready = True
    if client.memory.is_host:
        client.send(structs.ClientIdType.TRY_START)


def handle_room_menu_not_ready(client):
    """Take the ready flag back so the deck can still be changed."""
    client.send(structs.ClientIdType.NOT_READY)
    client.memory.is_ready = False
    utils.output(_("You are no longer ready."))
    display_room_menu(client)


@utils.ui_function
def handle_room_menu_kick(client):
    """Host only: remove a player, which needs CTOS_HS_KICK and a seat number."""
    users = getattr(client.room, "users", []) or []
    own_name = variables.config.get("nickname")
    menu = VerticalMenu(_("Remove a player"))
    removable = [user for user in users if user.get("name") != own_name]
    if not removable:
        menu.append_item(_("There is nobody else in the room."))
    for user in removable:
        menu.append_item(
            _("Remove {name}").format(name=user.get("name", "")),
            lambda pos=user.get("pos", 0), name=user.get("name", ""): send_kick(client, pos, name),
        )
    menu.append_item(_("Back"), lambda: display_room_menu(client))
    return menu


def send_kick(client, position, name):
    kick = structs.CtosKick()
    kick.pos = int(position)
    client.send(structs.ClientIdType.TRY_KICK, kick)
    utils.output(_("Asked the server to remove {name}.").format(name=name))
    display_room_menu(client)

@utils.ui_function
def handle_room_menu_select_deck(client):
    # make a menu with name, public decks, my decks, and the import options
    deck_menu = VerticalMenu(_("Select Deck"))
    deck_menu.append_item(_("Public Decks"), lambda: handle_room_menu_show_deck_menu(client, _("Public Decks"), variables.LOCAL_DATA_DIR / "decks"))
    deck_menu.append_item(_("My Decks"), lambda: handle_room_menu_show_deck_menu(client, _("My Decks"), variables.DECK_DIR))
    deck_menu.append_item(_("Import deck from deck string"), lambda: handle_import_deck_show_menu(client))
    deck_menu.append_item(_("Import all decks from YuGiOh MUD"), lambda: handle_import_all_decks(client))
    deck_menu.append_item(_("Back"), lambda: display_room_menu(client))
    return deck_menu

@utils.ui_function
def handle_room_menu_show_deck_menu(client, name, deck_dir):
    if not deck_dir.exists():
        logger.debug(f"Creating deck directory {deck_dir}")
        deck_dir.mkdir(parents=True, exist_ok=True)
    deck_menu = VerticalMenu(str(name))
    # loop through all files found in variables.DECK_DIR
    for deck_file in sorted(deck_dir.iterdir(), key=lambda path: path.stem.lower()):
        if not deck_file.is_file() or deck_file.suffix.lower() not in (".json", ".ydke"):
            continue
        # give full path to the deck file
        deck_menu.append_item(str(deck_file.stem), lambda deck_file=deck_file: handle_deck_menu_select_deck(client, deck_file))
    deck_menu.append_item(_("Back"), lambda: handle_room_menu_select_deck(client))
    return deck_menu


@utils.ui_function
def handle_room_menu_check_deck_against_banlist(client):
    menu = VerticalMenu(_("Check deck against room banlist"))
    menu.append_item(_("Public Decks"), lambda: handle_room_menu_show_banlist_deck_menu(client, _("Public Decks"), variables.LOCAL_DATA_DIR / "decks"))
    menu.append_item(_("My Decks"), lambda: handle_room_menu_show_banlist_deck_menu(client, _("My Decks"), variables.DECK_DIR))
    menu.append_item(_("Back"), lambda: display_room_menu(client))
    return menu


@utils.ui_function
def handle_room_menu_show_banlist_deck_menu(client, name, deck_dir):
    if not deck_dir.exists():
        deck_dir.mkdir(parents=True, exist_ok=True)
    deck_menu = VerticalMenu(str(name))
    deck_files = [path for path in sorted(deck_dir.iterdir(), key=lambda path: path.stem.lower()) if path.is_file() and path.suffix.lower() in (".json", ".ydke")]
    if not deck_files:
        deck_menu.append_item(_("No decks found."), None)
    for deck_file in deck_files:
        deck_menu.append_item(str(deck_file.stem), lambda deck_file=deck_file: show_room_banlist_check_result(client, deck_file))
    deck_menu.append_item(_("Back"), lambda: handle_room_menu_check_deck_against_banlist(client))
    return deck_menu


@utils.ui_function
def show_room_banlist_check_result(client, deck_file):
    parsed_deck = _load_deck_file(deck_file)
    banlist = _get_room_banlist(client.room)
    banlist_name = getattr(banlist, "name", None) or _("Unknown banlist")
    is_allowed, reason = banlist.is_deck_allowed(parsed_deck)
    menu = VerticalMenu(_("Banlist result"))
    if is_allowed:
        menu.append_item(_("Deck {name} is legal for {banlist}.").format(name=deck_file.stem, banlist=banlist_name), None)
    else:
        menu.append_item(_("Deck {name} is not legal for {banlist}.").format(name=deck_file.stem, banlist=banlist_name), None)
        for card_code, card_info in reason.items():
            card = Card(card_code)
            menu.append_item(
                _("{card} is limited to {limit} and you have {found}.").format(
                    card=card.get_name(), limit=card_info.limit, found=card_info.found
                ),
                None,
            )
    menu.append_item(_("Back"), lambda: handle_room_menu_check_deck_against_banlist(client))
    return menu

@utils.ui_function
def handle_import_all_decks(client):
    deck_menu = VerticalMenu(_("Import all decks"))
    deck_menu.append_item(_("This will import all the decks you have from the AllInAccess YuGiOh MUD!"), lambda: None)
    deck_menu.append_item(_("This will remove all current decks you have!"), lambda: None)
    deck_menu.append_item(_("To continue, please put in your MUD username and password"), lambda: None)
    username_input = deck_menu.append_item(wx.TextCtrl, label=_("Username"))
    password_input = deck_menu.append_item(wx.TextCtrl, label=_("Password"))
    deck_menu.append_item(_("Import"), lambda: handle_import_all_decks_import(client, username_input.GetValue(), password_input.GetValue()))
    deck_menu.append_item(_("Back"), lambda: handle_room_menu_select_deck(client))
    return deck_menu

def handle_import_all_decks_import(client, username, password):
    if not username:
        sm = StatusMessage(_("You must provide a username"), lambda: handle_import_all_decks(client))
        sm.show()
        return
    if not password:
        sm = StatusMessage(_("You must provide a password"), lambda: handle_import_all_decks(client))
        sm.show()
        return
    # get the list of decks from the MUD
    url = "https://allinaccess.com/game/decklist.php"
    logger.debug(f"Getting decks from {url}")
    result = requests.post(url, data={"username": username, "password": password})
    body = result.json()
    if result.status_code != 200 or "error" in body:
        logger.warning(f"Unable to import decks: {result.status_code} {body}")
        sm = StatusMessage(_("Unable to import decks: {error}").format(error=body["error"]), lambda: handle_import_all_decks(client))
        sm.show()
        return
    amount_of_decks_to_import = len(body)
    if amount_of_decks_to_import == 0:
        sm = StatusMessage(_("No decks to import"), lambda: handle_room_menu_select_deck(client))
        sm.show()
        return
    logger.debug(f"Got {amount_of_decks_to_import} decks")
    logger.debug("Removing all current decks")
    for deck_file in variables.DECK_DIR.iterdir():
        deck_file.unlink()
    logger.debug("Importing decks")
    for deck_info in body:
        logger.debug(f"Importing deck: {deck_info['name']} {deck_info['url']}")
        deck = ydke.Deck.from_ydke(deck_info["url"])
        deck_file = Path(variables.DECK_DIR / f"{utils.sanitize_filename(deck_info['name'])}.json")
        with open(deck_file, "w") as f:
            f.write(deck.to_json())
    # if amount_of_decks_to_import is not equal to the amount of files in the decks folder, show an error
    if amount_of_decks_to_import != len(list(variables.DECK_DIR.iterdir())):
        logger.warning(f"Not all decks were imported: {amount_of_decks_to_import} != {len(list(variables.DECK_DIR.iterdir()))}")
        sm = StatusMessage(_("Unable to import all decks - only some were imported."), lambda: handle_room_menu_select_deck(client))
        sm.show()
        return
    logger.debug("Decks imported")
    sm = StatusMessage(_("{count} decks imported").format(count=amount_of_decks_to_import), lambda: handle_room_menu_select_deck(client))
    sm.show()



@utils.ui_function
def handle_deck_menu_select_deck(client, deck_file):
    logger.debug(f"Loading deck {str(deck_file)}")
    utils.output(_("Loading deck {name}").format(name=deck_file.stem))
    parsed_deck = _load_deck_file(deck_file)
    logger.debug(f"Deck: {parsed_deck}")
    # check against room banlist
    banlist = _get_room_banlist(client.room)
    is_allowed, reason = banlist.is_deck_allowed(parsed_deck)
    logger.debug(f"Deck is allowed: {is_allowed} {reason}")
    if not is_allowed:
        # convert the reason into a string
        banned_deck_message = VerticalMenu(_("Deck is not allowed"))
        banned_deck_message.append_item(_("Deck is not allowed"), lambda: None)
        for card_code, card_info in reason.items():
            card = Card(card_code)
            banned_deck_message.append_item(_("{card} is limited to {limit} and you have {found} in your deck.\n").format(card=card.name, limit=card_info.limit, found=card_info.found), lambda: None)
        banned_deck_message.append_item(_("Back"), lambda: handle_room_menu_select_deck(client))
        return banned_deck_message
    deck = structs.Deck()
    deck.set_main_deck(parsed_deck.cards)
    deck.set_side_deck(parsed_deck.side)
    client.send(structs.ClientIdType.UPDATE_DECK, deck)
    client.memory.deck = deck
    client.memory.parsed_deck = parsed_deck
    utils.output(_("Deck {name} loaded").format(name=deck_file.stem))
    display_room_menu(client)
    return


def _load_deck_file(deck_file):
    with open(deck_file, "r") as f:
        if deck_file.suffix == ".ydke":
            return ydke.Deck.from_ydke(f.read())
        return ydke.Deck.from_json(f.read())

@utils.ui_function
def handle_import_deck_show_menu(client):
    # it should be a vertical menu, with 2 input boxes. Name and ydke deck string
    deck_import_menu = VerticalMenu(_("Import Deck"))
    name_input = deck_import_menu.append_item(wx.TextCtrl, label=_("Deck name"))
    deck_input = deck_import_menu.append_item(wx.TextCtrl, label=_("YDKE Deck string"))
    deck_import_menu.append_item(_("Import"), lambda: handle_deck_import_import_deck(client, name_input.GetValue(), deck_input.GetValue()))
    deck_import_menu.append_item(_("Back"), lambda: handle_room_menu_select_deck(client))
    return deck_import_menu

def handle_deck_import_import_deck(client, name, deck_string):
    if not name:
        sm = StatusMessage(_("You must provide a name for the deck"), lambda: handle_import_deck_show_menu(client))
        sm.show()
        return
    sanitized_name = utils.sanitize_filename(name).strip()
    if not sanitized_name:
        sm = StatusMessage(_("Deck name can only contain letters and numbers"), lambda: handle_import_deck_show_menu(client))
        sm.show()
        return
    if not deck_string:
        sm = StatusMessage(_("You must provide a deck string"), lambda: handle_import_deck_show_menu(client))
        sm.show()
        return
    if not deck_string.startswith("ydke"):
        sm = StatusMessage(_("Deck string doesn't seem to be a valid deck string"), lambda: handle_import_deck_show_menu(client))
        sm.show()
        return
    try:
        deck = ydke.Deck.from_ydke(deck_string)
    except ydke.URLParseError:
        sm = StatusMessage(_("Deck string doesn't seem to be a valid deck string"), lambda: handle_import_deck_show_menu(client))
        sm.show()
        return
    deck_file = Path(variables.DECK_DIR / f"{sanitized_name}.json")
    with open(deck_file, "w") as f:
        f.write(deck.to_json())
    sm = StatusMessage(_("Deck {name} imported").format(name=sanitized_name), lambda: handle_room_menu_select_deck(client))
    sm.show()


def handle_add_bot_as_opponent(client):
    utils.get_ui_stack().clear_ui_stack()
    if len(client.room.users) >= 2:
        sm = StatusMessage(_("There are already 2 players in the room"), lambda: display_room_menu(client))
        sm.show()
        return
    available_decks = _get_available_bot_decks()
    if not available_decks:
        sm = StatusMessage(_("No bot decks found."), lambda: display_room_menu(client))
        sm.show()
        return
    bot_menu = VerticalMenu(_("Select bot deck"))
    bot_menu.append_item(_("Random"), lambda: add_bot_to_room(client, "", available_decks))
    for label, deck in _bot_choices(available_decks):
        bot_menu.append_item(str(label), lambda deck=deck: add_bot_to_room(client, deck, available_decks))
    bot_menu.append_item(_("Back"), lambda: display_room_menu(client))
    utils.get_ui_stack().push_ui(bot_menu)


def _install_root() -> Path:
    # Resolved per call rather than at import so the location stays overridable.
    return Path(__file__).parent.parent.parent


def _get_available_bot_decks() -> list[str]:
    """The WindBot deck keys this build can actually pilot.

    Reported as keys rather than file names: a deck file with no executor makes
    WindBot fall back to a random deck, so offering it would be a lie.
    """
    from bot import deck_catalogue

    decks_dir = _install_root() / "Decks"
    if not decks_dir.exists():
        return []
    available = {path.stem for path in decks_dir.glob("*.ydk")}
    return sorted(
        key for key, deck_file in deck_catalogue.KEY_TO_DECK_FILE.items()
        if deck_file in available
    )


def _load_bot_catalogue() -> list[dict]:
    """WindBot's own bots.json: the deck names a player would recognise.

    The menu used to read raw file names off disk, so a blind player chose
    between "AI_BlueEyes" and "AI_Dragun" with no idea how hard either is.
    WindBot ships the curated names and difficulties in this file.
    """
    try:
        return json.loads((_install_root() / "bots.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Could not read bots.json; falling back to the deck file names")
        return []


def _bot_choices(available_decks) -> list[tuple[str, str]]:
    """Pair each playable bot with something worth reading out.

    bots.json holds the names a player recognises and a difficulty; the menu
    used to read raw file names off disk instead.
    """
    playable = [str(deck) for deck in available_decks]
    catalogue = {}
    for entry in _load_bot_catalogue():
        if isinstance(entry, dict) and entry.get("deck"):
            catalogue.setdefault(str(entry["deck"]), entry)

    choices = []
    for deck in playable:
        entry = catalogue.get(deck, {})
        name = entry.get("name") or deck
        difficulty = entry.get("difficulty")
        if isinstance(difficulty, int):
            label = _("{name}, difficulty {difficulty}").format(name=name, difficulty=difficulty)
        else:
            label = str(name)
        choices.append((label, deck))
    choices.sort(key=lambda choice: choice[0].lower())
    return choices


def add_bot_to_room(client, deck="", available_decks=[]):
    if len(client.room.users) >= 2:
        sm = StatusMessage(_("There are already 2 players in the room"), lambda: display_room_menu(client))
        sm.show()
        return
    if not deck and available_decks:
        deck = random.choice(available_decks)
    try:
        from bot.launcher import launch_bot_for_room
        launch_bot_for_room(client, deck=deck)
        utils.get_ui_stack().clear_ui_stack()
        utils.output(_("Bot added to room"))
    except Exception as e:
        logger.exception("Failed to launch bot")
        sm = StatusMessage(
            _("Unable to add a bot at this time. {reason}").format(reason=str(e)),
            lambda: display_room_menu(client),
        )
        sm.show()
        return
    return display_room_menu(client)


def handle_me_disconnect(client):
    # we should probably send a packet here, but don't know if it's needed, or if closing the socket is enough.
    client.disconnect()
    return server_ui.server_main_menu(client.server)
