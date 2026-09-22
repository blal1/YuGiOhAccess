import wx
import logging
from core import utils
from core.i18n import _
from game.servers import get_servers
from ui.base_ui import InputUI, StatusMessage, VerticalMenu, WaitUI, NumberInputUI

from game.client import Client
from game.edo import banlists

from core import variables
logger = logging.getLogger(__name__)

@utils.ui_function
def server_selection_menu():
    servers = get_servers()
    if isinstance(variables.DEV_OPTIONS.server, int):
        server = servers[variables.DEV_OPTIONS.server]
        logger.debug(f"Connecting to {server}")
        server_main_menu(server)
        return
    server_selection_menu = VerticalMenu(_("Server Menu"))
    for server in servers:
        server_selection_menu.append_item(str(server.name), lambda server=server: server_main_menu(server))
    server_selection_menu.append_cancel_item(_("Back"), utils.get_main_menu_function)
    return server_selection_menu

@utils.ui_function
def server_main_menu(server):
    wait_ui = WaitUI(_("Connecting to server"), server.is_available)
    result = wait_ui.show()
    if not result:
        sm = StatusMessage(_("Server is not available"), server_selection_menu)
        sm.show()
        return
    # we know we can connect to the server. It's stored in the server variable.
    # make a menu to either create a room or join a room
    if variables.DEV_OPTIONS.action:
        if variables.DEV_OPTIONS.action == "create":
            create_room_on_server(server, {
                "name": "",
                "password": variables.DEV_OPTIONS.password or "",
                "notes": "",
            })
            return
        if variables.DEV_OPTIONS.action == "join":
            join_room_final(server, variables.DEV_OPTIONS.id, variables.DEV_OPTIONS.password)
            return
    utils.get_discord_presence_manager().update_presence(
        state=_("Connected to {name}").format(name=server.name)
    )
    room_menu = VerticalMenu(_("Connected to {name}").format(name=server.name))
    room_menu.append_item(_("Create Room"), lambda: create_room(server))
    room_menu.append_item(_("Join Room"), lambda: join_room_ask_for_id(server))
    room_menu.append_item(_("Spectate Room"), lambda: spectate_room_ask_for_id(server))
    room_menu.append_item(_("List Rooms"), lambda: list_rooms(server))
    room_menu.append_item(_("Disconnect"), server_selection_menu)
    return room_menu

@utils.ui_function
def create_room(server):
    banlist_manager = banlists.BanlistManager()
    # we know we can connect to the server. It's stored in the server variable.
    room_menu = VerticalMenu(_("Room Settings"))
    room_menu.append_item(_("Room Settings"), None)
    notes = room_menu.append_item(wx.TextCtrl, None, label=_("Room notes"))
    password = room_menu.append_item(wx.TextCtrl, None, label=_("Room password (leave empty to make a public room)"), style=wx.TE_PASSWORD)
    banlist = room_menu.append_item(wx.Choice, label=_("Banlist"), choices=banlist_manager.get_banlist_names())
    banlist.Bind(wx.EVT_KEY_DOWN, lambda event: banlist_change_choice(event, banlist))
    banlist.SetSelection(0)
    match_mode = room_menu.append_item(wx.CheckBox, label=_("Match best of 3"))
    tag_duel = room_menu.append_item(wx.CheckBox, label=_("Tag duel 2 vs 2"))
    room_menu.append_item(_("Create Room"), lambda: create_room_on_server(server, {
        "name": "",
        "password": password.GetValue(),
        "notes": notes.GetValue().strip(),
        "banlist": banlist.GetString(banlist.GetSelection()),
        "best_of": 3 if match_mode.GetValue() else 1,
        "team_count": 2 if tag_duel.GetValue() else 1,
    }))
    room_menu.append_cancel_item(_("Back"), lambda: server_main_menu(server))
    return room_menu

def banlist_change_choice(event, choicer):
    # if key is left arrow, go to the previous choice
    if event.GetKeyCode() == wx.WXK_LEFT:
        new_choice = choicer.GetSelection() - 1
        if new_choice < 0:
            new_choice = choicer.GetCount() - 1
        choicer.SetSelection(new_choice)
        utils.output(str(choicer.GetString(choicer.GetSelection())))
    # if key is right arrow, go to the next choice
    if event.GetKeyCode() == wx.WXK_RIGHT:
        new_choice = choicer.GetSelection() + 1
        if new_choice >= choicer.GetCount():
            new_choice = 0
        choicer.SetSelection(new_choice)
        utils.output(str(choicer.GetString(choicer.GetSelection())))
    else:
        event.Skip()

def create_room_on_server(server, room_settings):
    logger.debug(f"Creating room with settings {room_settings} on {server}")
    c = Client.create_room(server, room_settings)
    if not c:
        return
    logger.debug(f"Created room {c}")
    # store the password in memory if we need it later
    if room_settings["password"]:
        c.memory.room_password = room_settings["password"]
    c.memory.is_host = True
    # the room will automatically be shown, by packets being received.


def room_capacity(room):
    capacity_fn = getattr(room, "capacity", None)
    if callable(capacity_fn):
        try:
            raw_capacity = capacity_fn()
            if isinstance(raw_capacity, (int, str)):
                capacity = int(raw_capacity)
            else:
                capacity = 0
            if capacity > 0:
                return capacity
        except (TypeError, ValueError):
            pass
    try:
        team1 = int(room.team1)
        team2 = int(room.team2)
        if team1 > 0 and team2 > 0:
            return team1 + team2
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        return int(room.host_info.t0_count) + int(room.host_info.t1_count)
    except (AttributeError, TypeError, ValueError):
        pass
    return 2


def room_user_count(room):
    duelist_users_fn = getattr(room, "duelist_users", None)
    if callable(duelist_users_fn):
        try:
            duelists = duelist_users_fn()
            if isinstance(duelists, (list, tuple)):
                return len(duelists)
        except TypeError:
            pass
    users = getattr(room, "users", [])
    capacity = room_capacity(room)
    duelists = []
    for user in users:
        try:
            pos = int(user.get("pos", user.get("position")))
        except (AttributeError, TypeError, ValueError):
            return len(users)
        if pos < capacity:
            duelists.append(user)
    return len(duelists)

def join_room_ask_for_id(server):
    # ask for the room id, keeping in mind that it should be a number
    room_id_input = NumberInputUI(_("Enter room id"))
    room_id = room_id_input.show()
    if not room_id:
        server_main_menu(server)
        return
    join_room(server, room_id)


def spectate_room_ask_for_id(server):
    room_id_input = NumberInputUI(_("Enter room id to spectate"))
    room_id = room_id_input.show()
    if not room_id:
        server_main_menu(server)
        return
    spectate_room(server, room_id)


@utils.ui_function
def list_rooms(server):
    rooms = server.list_rooms()
    if not rooms:
        sm = StatusMessage(_("No rooms available"), lambda: server_main_menu(server))
        sm.show()
        return
    room_menu = VerticalMenu(_("Rooms on {name}").format(name=server.name))
    for room in rooms:
        room_printable = f"{room.roomid}, "
        room_printable += _("status: {status}, ").format(status=room.istart)
        if room.needpass:
            room_printable += _("needs password, ")
        if room.roomname:
            room_printable += f" name: {room.roomname}, "
        if room.roomnotes:
            room_printable += f"notes: {room.roomnotes}, "
        room_printable += f"{room.team1} vs {room.team2}, "
        if room.best_of == 3:
            room_printable += _("match, ")
        if room_capacity(room) == 4:
            room_printable += _("tag duel, ")
        room_printable += _("Duelists: {current}/{capacity}, ").format(current=room_user_count(room), capacity=room_capacity(room))
        try:
            spectators = len(room.spectator_users())
        except AttributeError:
            spectators = 0
        if spectators:
            room_printable += _("spectators: {count}, ").format(count=spectators)
        room_printable += f"Players: {room.print_players()}"
        room_printable += f"Time limit: {round(room.time_limit/60, 2)} minutes, "
        if room.start_lp != 8000:
            room_printable += f"Starting LP: {room.start_lp}, "
        if room.start_hand != 5:
            room_printable += f"Starting hand: {room.start_hand}, "
        if room.draw_count != 1:
            room_printable += f"Draw count: {room.draw_count}, "
        room_menu.append_item(str(room_printable), lambda room=room: room_action_menu(server, room))
    room_menu.append_cancel_item(_("Back"), lambda: server_main_menu(server))
    return room_menu


@utils.ui_function
def room_action_menu(server, room):
    menu = VerticalMenu(_("Room {id}").format(id=room.roomid))
    if room.istart == "waiting" and room_user_count(room) < room_capacity(room):
        menu.append_item(_("Join as duelist"), lambda: join_room(server, room.roomid))
    menu.append_item(_("Spectate"), lambda: spectate_room(server, room.roomid))
    menu.append_cancel_item(_("Back"), lambda: list_rooms(server))
    return menu


def join_room(server, id, password=None):
    logger.debug(f"Joining room {id} on {server}")
    room = server.get_room(id)
    if not room:
        sm = StatusMessage(_("Room not found"), lambda: server_main_menu(server))
        sm.show()
        return
    logger.debug(f"Room found: {room}")
    if room.istart != "waiting":
        sm = StatusMessage(_("Room is not waiting"), lambda: server_main_menu(server))
        sm.show()
        return
    if room.needpass and not password:
        logger.debug("Room needs password")
        password_input = InputUI(_("Enter room password"))
        password = password_input.show()
        if not password:
            logger.debug("No password entered")
            server_main_menu(server)
            return
    if room_user_count(room) >= room_capacity(room):
        sm = StatusMessage(_("Room is full"), lambda: server_main_menu(server))
        sm.show()
        return
    logger.debug(f"Joining room {room}")
    join_room_final(server, room.roomid, password)


def spectate_room(server, id, password=None):
    logger.debug(f"Spectating room {id} on {server}")
    room = server.get_room(id)
    if not room:
        sm = StatusMessage(_("Room not found"), lambda: server_main_menu(server))
        sm.show()
        return
    if room.needpass and not password:
        password_input = InputUI(_("Enter room password"))
        password = password_input.show()
        if not password:
            server_main_menu(server)
            return
    join_room_final(server, room.roomid, password, as_observer=True)


def join_room_final(server, id, password, as_observer=False):
    c = Client.join_room(server, id, password, as_observer=as_observer)
    if not c:
        sm = StatusMessage(_("Password incorrect"), lambda: server_main_menu(server))
        sm.show()
        return
    c.memory.is_host = False
    c.memory.is_observer = as_observer
    c.memory.room_password = password
    if as_observer:
        utils.output(_("Joined room as spectator"))
    logger.info(f"Joined room {c}")
