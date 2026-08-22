class DotDict(dict):
    """Dictionary that supports dot notation access to keys."""
    def __hasattr__(self, attr):
        return attr in self

    def __getattr__(self, attr):
        try:
            return self[attr]
        except KeyError:
            raise AttributeError(f"'DotDict' object has no attribute '{attr}'")

    def __setattr__(self, key, value):
        self[key] = value
        
