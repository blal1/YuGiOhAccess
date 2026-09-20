import logging
import json
import sqlite3
import time
import requests

from pathlib import Path

from core import variables
from core.exceptions import LanguageException

logger = logging.getLogger(__name__)

class LanguageHandler:
    languages = dict()
    primary_language = ''
    DEFAULT_LANGUAGES = {
        "english": "en",
        "german": "de",
        "japanese": "ja",
        "spanish": "es",
        "portuguese": "pt",
        "italian": "it",
        "french": "fr",
        "thai": "th",
    }
    MULTILINGUAL_LANGUAGE_FOLDERS = {
        "french": "Français",
        "german": "Deutsch",
        "spanish": "Español",
        "italian": "Italiano",
        "portuguese": "Português",
    }
    CARD_TRANSLATION_LANGUAGES = {
        "french": "fr",
        "german": "de",
        "italian": "it",
        "portuguese": "pt",
    }

    def __init__(self):
        self.strings_path = Path(Path(variables.LOCAL_DATA_DIR) / "locales")
        self.card_database_dir = Path(Path(variables.APP_DATA_DIR) / "sync" / "databases2" / "content")
        self.multilingual_data_dir = Path(variables.APP_DATA_DIR) / "sync" / "languages" / "content"
        self.card_translation_dir = Path(variables.APP_DATA_DIR) / "sync" / "card_translations"

    def add_available_languages(self):
        for lang, short in self.DEFAULT_LANGUAGES.items():
            if self.__strings_file_path(short, lang):
                self.add(lang, short)

    def add(self, lang, short):
        lang = lang.lower()
        short = short.lower()
        logger.info("Adding language "+lang+" with shortage "+short)
        try:
            language_information = {'short': short}
            language_information['strings'] = self.__parse_strings(short, lang)
            self.languages[lang] = language_information
        except LanguageException as e:
            logger.error("Failed to add language "+lang+": "+str(e))

    def connect_all_databases(self):
        for lang in self.languages.keys():
            logger.info("Connecting database for language "+lang)
            self.languages[lang]['db'] = self.__connect_database(lang)

    def __connect_database(self, lang=None):
        database_dir = self.__card_database_dir_for_language(lang)
        card_database_file = Path(database_dir / "cards.cdb")
        if not card_database_file.exists():
            raise LanguageException("cards.cdb not found in "+str(card_database_file.parent))
        cdb = sqlite3.connect(":memory:", check_same_thread=False)
        cdb.row_factory = sqlite3.Row
        cdb.create_function('UPPERCASE', 1, lambda s: s.upper())
        cdb.execute("ATTACH ? AS new", (str(card_database_file), ))
        cdb.execute("CREATE TABLE datas AS SELECT * FROM new.datas WHERE id<100000000")
        cdb.execute("CREATE TABLE texts AS SELECT * FROM new.texts WHERE id<100000000")
        cdb.execute("DETACH new")
        cdb.execute("CREATE UNIQUE INDEX idx_datas_id ON datas (id)")
        cdb.execute("CREATE UNIQUE INDEX idx_texts_id ON texts (id)")

        # getting all column names from cards.cdb
        cursor = cdb.execute("SELECT * FROM datas LIMIT 1")
        row = cursor.fetchone()
        columns = row.keys()
        cursor.close()

        extending_dbs  = Path(database_dir).glob('*.cdb')
        count = 0
        for p in extending_dbs:
            if p.name == 'cards.cdb':
                continue
            count += 1
            cdb.execute("ATTACH ? as new", (str(p), ))

            # getting all columns currently available in the merged db
            cursor = cdb.execute("SELECT * FROM new.datas LIMIT 1")
            row = cursor.fetchone()
            if not row:
                logger.warning("Database "+str(p)+" is empty")
                cursor.close()
                cdb.execute("DETACH new")
                continue
            new_columns = row.keys()
            cursor.close()

            # getting all columns which are available in both tables
            new_columns = [c for c in new_columns if c in columns]

            cdb.execute("INSERT OR REPLACE INTO datas ({0}) SELECT {0} FROM new.datas WHERE id<100000000".format(', '.join(new_columns)))
            cdb.execute("INSERT OR REPLACE INTO texts SELECT * FROM new.texts WHERE id<100000000")
            cdb.commit()
            cdb.execute("DETACH new")
        logger.info("Merged {count} databases into cards.cdb".format(count = count))
        return cdb

    def __card_database_dir_for_language(self, lang):
        if self.__has_multilingual_card_database(lang):
            return self.multilingual_data_dir / self.MULTILINGUAL_LANGUAGE_FOLDERS[lang]
        return self.card_database_dir

    def __has_multilingual_card_database(self, lang):
        if lang not in self.MULTILINGUAL_LANGUAGE_FOLDERS:
            return False
        translated_dir = self.multilingual_data_dir / self.MULTILINGUAL_LANGUAGE_FOLDERS[lang]
        return (translated_dir / "cards.cdb").exists()

    def __strings_file_path(self, language_short, lang=None):
        if lang in self.MULTILINGUAL_LANGUAGE_FOLDERS:
            translated_path = self.multilingual_data_dir / self.MULTILINGUAL_LANGUAGE_FOLDERS[lang] / "strings.conf"
            if translated_path.exists():
                return translated_path
        bundled_path = self.strings_path / language_short / "strings.conf"
        if bundled_path.exists():
            return bundled_path
        return None

    def __parse_strings(self, language_short, lang=None):
        strings_file_path = self.__strings_file_path(language_short, lang)
        if not strings_file_path:
            raise LanguageException(f"strings-{language_short}.conf not found.")
        fallback = {}
        if language_short != "en":
            fallback_path = self.__strings_file_path("en", "english")
            if fallback_path and fallback_path.exists():
                fallback = self.__parse_strings_file(fallback_path)
        strings = self.__parse_strings_file(strings_file_path)
        for category, values in fallback.items():
            strings.setdefault(category, {})
            for key, value in values.items():
                strings[category].setdefault(key, value)
        return strings

    def __parse_strings_file(self, strings_file_path):
        res = {}
        with open(strings_file_path, 'r', encoding='utf-8') as fp:
            for line in fp:
                line = line.rstrip('\n')
                if not line.startswith('!') or line.startswith('!setcode'):
                    continue
                type, id, s = line[1:].split(' ', 2)
                try:
                    if id.startswith('0x'):
                        id = int(id, 16)
                    else:
                        id = int(id)
                except ValueError:
                    logger.debug("Skipping non-numeric string id in %s: %s", strings_file_path, line)
                    continue
                if type not in res:
                    res[type] = {}
                res[type][id] = s.replace('\xa0', ' ')
        return res

    def is_loaded(self, language):
        return language in self.languages

    def set_primary_language(self, lang):
        if not self.is_loaded(lang):
            raise LanguageException("language "+lang+" not loaded and can therefore not be set as primary language")
        self.primary_language = lang
        self.ensure_card_translations(lang)

    def ensure_card_translations(self, lang):
        if self.__has_multilingual_card_database(lang):
            self.languages.setdefault(lang, {"short": self.DEFAULT_LANGUAGES.get(lang, lang)})
            self.languages[lang]["card_translations"] = {}
            return
        api_code = self.CARD_TRANSLATION_LANGUAGES.get(lang)
        if not api_code:
            return
        language = self.languages.setdefault(lang, {"short": api_code})
        if "card_translations" in language:
            return
        cached = self.__load_card_translation_cache(lang)
        if cached is None:
            cached = self.__download_card_translations(lang, api_code)
        language["card_translations"] = cached or {}

    def __load_card_translation_cache(self, lang):
        cache_file = self.card_translation_dir / f"{lang}.json"
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return {int(card_id): value for card_id, value in payload.get("cards", {}).items()}
        except (OSError, ValueError, TypeError) as e:
            logger.warning("Failed to load card translation cache for %s: %s", lang, e)
            return None

    def __download_card_translations(self, lang, api_code):
        url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?language={api_code}"
        try:
            logger.info("Downloading %s card translations from YGOPRODeck", lang)
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            cards = {}
            for card in response.json().get("data", []):
                card_id = card.get("id")
                if not card_id:
                    continue
                cards[int(card_id)] = {
                    "name": card.get("name", ""),
                    "desc": card.get("desc", ""),
                }
            self.card_translation_dir.mkdir(parents=True, exist_ok=True)
            cache_file = self.card_translation_dir / f"{lang}.json"
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"updated_at": int(time.time()), "cards": cards}, f, ensure_ascii=False)
            logger.info("Cached %d %s card translations", len(cards), lang)
            return cards
        except (requests.RequestException, ValueError, OSError) as e:
            logger.error("Failed to download %s card translations: %s", lang, e)
            return {}

    def get_card_translation(self, code):
        language = self.languages.get(self.primary_language, {})
        translations = language.get("card_translations") or {}
        return translations.get(int(code))

    def get_card_translations(self):
        language = self.languages.get(self.primary_language, {})
        return language.get("card_translations") or {}

    def get_language(self, lang):
        try:
            return self.languages[lang]
        except KeyError:
            raise LanguageException("language not found")

    def get_strings(self, lang):
        return self.get_language(lang)['strings']

    def get_cards_by_partial_name(self, name):
        translated = self.__get_translated_cards_by_partial_name(name)
        if translated:
            return translated
        name_pattern = f"%{name}%"
        cursor = self.cdb.execute('SELECT id, name FROM texts WHERE name LIKE ?', (name_pattern,))
        rows = cursor.fetchall()
        if not rows:
            return {}
        result = {}
        for row in rows:
            result[row['name']] = row['id']
        return result

    def __get_translated_cards_by_partial_name(self, name):
        language = self.languages.get(self.primary_language, {})
        translations = language.get("card_translations") or {}
        if not translations:
            return {}
        name = name.casefold()
        result = {}
        for card_id, card in translations.items():
            card_name = card.get("name", "")
            if name in card_name.casefold():
                result[card_name] = card_id
        return result
    
    @property
    def primary_database(self):
        return self.get_language(self.primary_language)['db']
    
    @property
    def strings(self):
        return self.get_strings(variables.config.get('language'))
    
    @property
    def cdb(self):
        return self.get_language(variables.config.get("language"))['db']
