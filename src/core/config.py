import logging
import json

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, defaults={}):
        self.defaults = defaults
        self.data = {}

    def load(self, path):
        logger.debug(f"Attemping to load config from {path}")
        try:
            self.path = path
            with open(path, "r") as f:
                self.data = json.load(f)
            logger.debug("Config loaded")
        except FileNotFoundError:
            logger.debug("Config file not found, using defaults")
            self.data = self.defaults
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to load config (using defaults): Decode Error: {e}")
            self.data = self.defaults

    def save(self, path=None):
        if not path:
            path = self.path
        logger.debug(f"Saving config to {path}")
        with open(path, "w") as f:
            json.dump(self.data, f, indent=4)

    def get(self, key, default=None):
        return self.data.get(key, self.defaults.get(key, default))
    
    def set(self, key, value):
        self.data[key] = value
        self.save()
