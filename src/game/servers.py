from core.i18n import _
from game.serverinfo import EdoServerInformation
import time


class TestingServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("Test Server"), "167.99.22.44", 7922, 7911)

class EUCasualServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("EU Central (Casual)"), "eu.projectignis.org", 7923, 7912)

class EUCompetitiveServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("EU Central (Competitive)"), "eu.projectignis.org", 7922, 7911)

class USCasualServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("US West (Casual)"), "us.projectignis.org", 7922, 7911)

class USCompetitiveServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("US West (Competitive)"), "us.projectignis.org", 7923, 7912)

class AsiaServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("Asia Central (Casual/Competitive)"), "ignis-room.ygopro.cn", 443, 44444)

class LocalServer(EdoServerInformation):
    def __init__(self):
        super().__init__(_("Local (Offline)"), "127.0.0.1", 7934, 7933)

    def is_available(self, unknown):
        from server.embedded import engine_status, is_running, start_local_server

        if not is_running():
            start_local_server(lobby_port=self.lobby_port, http_port=self.room_listing_port)
            deadline = time.time() + 1
            while time.time() < deadline:
                status = engine_status()
                if status.version or status.error:
                    break
                time.sleep(0.05)
        status = engine_status()
        if status.version or status.error or status.ocgcore_path:
            return is_running() and status.available
        return is_running()

    def engine_status(self):
        from server.embedded import engine_status

        return engine_status()


def get_servers():
    return [LocalServer(), TestingServer(), EUCasualServer(), EUCompetitiveServer(), USCasualServer(), USCompetitiveServer()]
