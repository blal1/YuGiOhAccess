import logging
import json

logger = logging.getLogger(__name__)

class Config:
    def __init__(self, defaults={}):
        self.defaults = defaults
        self.data = {}
        # Where this config came from, and where set() writes it back. Set by
        # load(); until then there is nowhere to save to, and a set() before
        # the first load used to raise AttributeError rather than say so.
        self.path = None

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
        if not path:
            # Losing a preference is bad; taking the application down over it
            # is worse. This only happens before the first load().
            logger.warning("Not saving the config: no path has been set yet")
            return
        logger.debug(f"Saving config to {path}")
        with open(path, "w") as f:
            json.dump(self.data, f, indent=4)

    def get(self, key, default=None):
        return self.data.get(key, self.defaults.get(key, default))
    
    def set(self, key, value):
        self.data[key] = value
        self.save()
