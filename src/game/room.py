import json

class EdoRoom:
    def __init__(self, payload):
        self.payload = payload

    # update the __getattribute__ method to allow for easy access to the payload
    def __getattribute__(self, name):
        try:
            return super().__getattribute__(name)
        except AttributeError:
            try:
                return self.payload[name]
            except KeyError:
                raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        
    def __str__(self):
        return json.dumps(self.payload, indent=4)
    
    def print_players(self):
        users = self.users
        result = ""
        for user in users:
            result += f"{user['name']}, "
        return result

    def capacity(self):
        try:
            team1 = int(self.team1)
            team2 = int(self.team2)
            if team1 > 0 and team2 > 0:
                return team1 + team2
        except (AttributeError, TypeError, ValueError):
            pass
        try:
            return int(self.host_info["t0_count"]) + int(self.host_info["t1_count"])
        except (AttributeError, KeyError, TypeError, ValueError):
            pass
        return 2

    def duelist_users(self):
        users = self.users
        capacity = self.capacity()
        duelists = []
        for user in users:
            try:
                pos = int(user.get("pos", user.get("position")))
            except (AttributeError, TypeError, ValueError):
                return users
            if pos < capacity:
                duelists.append(user)
        return duelists

    def spectator_users(self):
        users = self.users
        duelists = self.duelist_users()
        return [user for user in users if user not in duelists]
    
    def __eq__(self, other):
        return self.roomid == other.roomid and self.roomname == other.roomname and self.roomnotes == other.roomnotes and self.team1 == other.team1 and self.team2 == other.team2 and self.best_of == other.best_of
