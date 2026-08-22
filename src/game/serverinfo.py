"""An edopro server."""

import time
import socket
import logging
import requests

from game.room import EdoRoom

from core import variables

logger = logging.getLogger(__name__)

class EdoServerInformation:
    def __init__(self, name, address, room_listing_port, lobby_port):
        """Create a new server with the given name, address, and ports."""
        self.name = name
        self.address = address
        self.room_listing_port = room_listing_port
        self.lobby_port = lobby_port
        self.room_session = requests.Session()


    # check if the server is reachable. This includes making a minial request to the 2 ports.
    # make a header requests to the http, and a socket connection to the lobby port.
    def is_available(self, unknown):
        try:
            self.room_session.head(f"http://{self.resolve_hostname_to_ip()}:{self.room_listing_port}", timeout=1)
            with socket.create_connection((self.resolve_hostname_to_ip(), self.lobby_port), timeout=1):
                return True
        except requests.exceptions.RequestException:
            return False
        except socket.timeout:
            return False
        except ConnectionRefusedError:
            return False
        except Exception as e:
            logger.error(f"An error occurred while checking if the server is available, {e}", exc_info=True)
            return False
        
    def __str__(self):
        return f"{self.name} ({self.address}, {self.room_listing_port}, {self.lobby_port})"
    
    def __repr__(self):
        return self.__str__()
    
    def join_room(self, room_id):
        """Join the room with the given id."""
        # get the room json
        room_json = self._get_room_json()
        logger.debug(room_json[0])

    def get_room(self, room_id):
        """Get the room with the given id."""
        start = time.time()
        room_json = self._get_room_json()
        end = time.time()
        logger.debug(f"Getting room json took {end-start} seconds")
        if not room_json:
            return None
        try:
            start = time.time()
            room_gotten = EdoRoom([room for room in room_json if room["roomid"] == room_id][0])
            end = time.time()
            logger.debug(f"Getting room took {end-start} seconds")
            return room_gotten
        except IndexError:
            return None

    def list_rooms(self):
        """List the rooms on the server."""
        room_json = self._get_room_json() or []
        rooms = [EdoRoom(room) for room in room_json]
        rooms.sort(key=lambda room: len(room.duelist_users()), reverse=False)
        return rooms
    
    def _get_room_json(self, force_ip_refresh=False):
        """Get the room listing json from the server."""
        try:
            rooms = self.room_session.get(f"http://{self.resolve_hostname_to_ip(force_ip_refresh)}:{self.room_listing_port}").json()["rooms"]
            return rooms
        except Exception as e:
            if not force_ip_refresh:
                return self._get_room_json(force_ip_refresh=True)
            logger.error(f"An error occurred while getting room json, {e}", exc_info=True)

    def resolve_hostname_to_ip(self, required_refresh=False):
        """Resolve the hostname to an ip address."""
        # if the address already looks like an ip, just return it
        if self.address.replace(".", "").isnumeric():
            return self.address
        ip_cache = variables.config.get("ip_cache")
        if self.address in ip_cache and not required_refresh:
            return ip_cache[self.address]
        try:
            ip = socket.gethostbyname(self.address)
            ip_cache[self.address] = ip
            variables.config.set("ip_cache", ip_cache)
            return ip
        except Exception as e:
            logger.error(f"An error occurred while resolving hostname to ip, {e}", exc_info=True)
            return self.address
