class LanguageException(Exception):
    def __init__(self, message):
        super().__init__(message)

class CardNotFoundException(Exception):
    def __init__(self, message):
        super().__init__(message)    