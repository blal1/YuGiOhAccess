import logging

import wx

from core import utils
from core import variables
from core.i18n import _
from game.card.card import Card
from game.card import card_constants
from ui.base_ui import VerticalMenu, InputUI

logger = logging.getLogger(__name__)

SEARCH_LIMIT = 100

TYPE_FILTERS = {
    "monster": card_constants.TYPE.MONSTER,
    "spell": card_constants.TYPE.SPELL,
    "trap": card_constants.TYPE.TRAP,
    "normal": card_constants.TYPE.NORMAL,
    "effect": card_constants.TYPE.EFFECT,
    "fusion": card_constants.TYPE.FUSION,
    "ritual": card_constants.TYPE.RITUAL,
    "synchro": card_constants.TYPE.SYNCHRO,
    "xyz": card_constants.TYPE.XYZ,
    "xzy": card_constants.TYPE.XYZ,
    "pendulum": card_constants.TYPE.PENDULUM,
    "link": card_constants.TYPE.LINK,
    "tuner": card_constants.TYPE.TUNER,
    "toon": card_constants.TYPE.TOON,
    "spirit": card_constants.TYPE.SPIRIT,
    "union": card_constants.TYPE.UNION,
    "gemini": card_constants.TYPE.DUAL,
    "dual": card_constants.TYPE.DUAL,
    "flip": card_constants.TYPE.FLIP,
    "quick-play": card_constants.TYPE.QUICKPLAY,
    "quickplay": card_constants.TYPE.QUICKPLAY,
    "continuous": card_constants.TYPE.CONTINUOUS,
    "equip": card_constants.TYPE.EQUIP,
    "field": card_constants.TYPE.FIELD,
    "counter": card_constants.TYPE.COUNTER,
    "extra": card_constants.TYPE.EXTRA,
}

ATTRIBUTE_FILTERS = {
    "earth": 0x01,
    "water": 0x02,
    "fire": 0x04,
    "wind": 0x08,
    "light": 0x10,
    "dark": 0x20,
    "divine": 0x40,
}

RACE_FILTERS = {
    "warrior": 0x1,
    "spellcaster": 0x2,
    "fairy": 0x4,
    "fiend": 0x8,
    "zombie": 0x10,
    "machine": 0x20,
    "aqua": 0x40,
    "pyro": 0x80,
    "rock": 0x100,
    "winged beast": 0x200,
    "plant": 0x400,
    "insect": 0x800,
    "thunder": 0x1000,
    "dragon": 0x2000,
    "beast": 0x4000,
    "beast-warrior": 0x8000,
    "beast warrior": 0x8000,
    "dinosaur": 0x10000,
    "fish": 0x20000,
    "sea serpent": 0x40000,
    "reptile": 0x80000,
    "psychic": 0x100000,
    "divine-beast": 0x200000,
    "divine beast": 0x200000,
    "creator-god": 0x400000,
    "creator god": 0x400000,
    "wyrm": 0x800000,
    "cyberse": 0x1000000,
    "illusion": 0x2000000,
}


@utils.ui_function
def card_search_menu(return_to=None):
    if not return_to:
        from ui.main_ui import main_menu_view
        return_to = main_menu_view
    menu = VerticalMenu(_("Card Search"))
    menu.set_help_text(_("Search the card database by name, description, type, attribute, or race."))
    menu.append_item(_("Search by name"), lambda: search_by_name(return_to))
    menu.append_item(_("Search by description"), lambda: search_by_description(return_to))
    menu.append_item(_("Advanced search"), lambda: advanced_search(return_to))
    menu.append_item(_("Back"), return_to)
    return menu


@utils.ui_function
def search_by_name(return_to):
    query_input = InputUI(_("Card name"))
    query = query_input.show()
    if not query:
        card_search_menu(return_to)
        return
    return show_search_results(return_to, name_query=query)


@utils.ui_function
def search_by_description(return_to):
    query_input = InputUI(_("Card description text"))
    query = query_input.show()
    if not query:
        card_search_menu(return_to)
        return
    return show_search_results(return_to, description_query=query)


@utils.ui_function
def advanced_search(return_to):
    name_query = InputUI(_("Card name, or leave empty")).show() or ""
    description_query = InputUI(_("Description text, or leave empty")).show() or ""
    type_query = InputUI(_("Type, or leave empty")).show() or ""
    attribute_query = InputUI(_("Attribute, or leave empty")).show() or ""
    race_query = InputUI(_("Race, or leave empty")).show() or ""
    return show_search_results(
        return_to,
        name_query=name_query,
        description_query=description_query,
        type_query=type_query,
        attribute_query=attribute_query,
        race_query=race_query,
    )


@utils.ui_function
def show_search_results(return_to, name_query="", description_query="", type_query="", attribute_query="", race_query=""):
    try:
        rows = _search_cards(name_query, description_query, type_query, attribute_query, race_query)
    except ValueError as exc:
        utils.output(_("{error}").format(error=str(exc)))
        card_search_menu(return_to)
        return
    if not rows:
        utils.output(_("No cards found."))
        card_search_menu(return_to)
        return
    return CardSearchResultsUI(return_to, rows)


class CardSearchResultsUI(wx.Panel):
    def __init__(self, return_to, rows):
        super().__init__(wx.GetTopLevelWindows()[0], style=wx.WANTS_CHARS, name=_("Card search results"))
        self.return_to = return_to
        self.rows = rows
        self.current_index = 0
        self.cards = [_card_from_result_row(row) for row in rows]

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.summary = wx.StaticText(self, label="")
        self.summary.SetName(_("Current result"))
        sizer.Add(self.summary, 0, wx.EXPAND | wx.ALL, 6)

        self.result_list = wx.ListBox(self, choices=[_format_result_label(code, name) for code, name in self.cards], style=wx.WANTS_CHARS)
        self.result_list.SetName(_("Card results"))
        self.result_list.SetToolTip(_("Use up and down to choose a card. Press Enter to open details, or Space to read all details."))
        sizer.Add(self.result_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

        self.details = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.WANTS_CHARS)
        self.details.SetName(_("Card details"))
        self.details.SetToolTip(_("Read-only card details for the selected card."))
        sizer.Add(self.details, 2, wx.EXPAND | wx.ALL, 6)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.previous_button = wx.Button(self, label=_("Previous"))
        self.read_button = wx.Button(self, label=_("Open details"))
        self.next_button = wx.Button(self, label=_("Next"))
        self.back_button = wx.Button(self, label=_("Back"))
        for button in (self.previous_button, self.read_button, self.next_button, self.back_button):
            buttons.Add(button, 0, wx.ALL, 4)
        sizer.Add(buttons, 0, wx.ALIGN_CENTER)
        self.SetSizer(sizer)

        self.result_list.Bind(wx.EVT_LISTBOX, self.on_result_selected)
        self.result_list.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.details.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.previous_button.Bind(wx.EVT_BUTTON, lambda event: self.move_selection(-1))
        self.read_button.Bind(wx.EVT_BUTTON, lambda event: self.open_current_detail())
        self.next_button.Bind(wx.EVT_BUTTON, lambda event: self.move_selection(1))
        self.back_button.Bind(wx.EVT_BUTTON, lambda event: self.go_back())
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.result_list.SetSelection(0)
        self.update_current_card(announce=True)

    def on_result_selected(self, event):
        selection = self.result_list.GetSelection()
        if selection >= 0:
            self.current_index = selection
            self.update_current_card(announce=True)

    def move_selection(self, delta):
        if not self.cards:
            return
        self.current_index = (self.current_index + delta) % len(self.cards)
        self.result_list.SetSelection(self.current_index)
        self.update_current_card(announce=True)
        self.result_list.SetFocus()

    def update_current_card(self, announce=False):
        code, name = self.cards[self.current_index]
        header = _("{position} of {count}: {name}, {summary}").format(
            position=self.current_index + 1,
            count=len(self.cards),
            name=name,
            summary=_format_card_summary(code),
        )
        self.summary.SetLabel(header)
        detail = _get_card_detail_text(code)
        self.details.SetValue(detail)
        self.previous_button.Enable(len(self.cards) > 1)
        self.next_button.Enable(len(self.cards) > 1)
        if announce:
            utils.output(header)

    def read_current_detail(self):
        code, _name = self.cards[self.current_index]
        utils.output(_get_card_detail_text(code))

    def open_current_detail(self):
        code, name = self.cards[self.current_index]
        utils.get_ui_stack().push_ui(CardDetailReaderUI(code, name))

    def go_back(self):
        card_search_menu(self.return_to)

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN:
            self.open_current_detail()
            return
        if key == wx.WXK_SPACE:
            self.read_current_detail()
            return
        if key == wx.WXK_LEFT:
            self.move_selection(-1)
            return
        if key == wx.WXK_RIGHT:
            self.move_selection(1)
            return
        if key == wx.WXK_ESCAPE:
            self.go_back()
            return
        if key == wx.WXK_F1:
            utils.output(_("Card results. Use up and down to choose a card, Enter to open details, Space to read all details, and Escape to go back."))
            return
        event.Skip()


class CardDetailReaderUI(wx.Panel):
    def __init__(self, code, name=None):
        super().__init__(wx.GetTopLevelWindows()[0], style=wx.WANTS_CHARS, name=_("Card details"))
        self.code = code
        self.card_name = name or ""
        self.detail_text = _get_card_detail_text(code)
        self.lines = _split_card_detail_lines(self.detail_text)
        self.current_line = 0

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.header = wx.StaticText(self, label=_("{name} details").format(name=self.card_name or _("Card")))
        self.header.SetName(_("Card detail header"))
        sizer.Add(self.header, 0, wx.EXPAND | wx.ALL, 6)

        self.line_label = wx.StaticText(self, label="")
        self.line_label.SetName(_("Current detail line"))
        sizer.Add(self.line_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.details = wx.TextCtrl(self, value=self.detail_text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.WANTS_CHARS)
        self.details.SetName(_("Full card text"))
        self.details.SetToolTip(_("Use up and down to read one line at a time. Press Space to read the full card."))
        sizer.Add(self.details, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.previous_line_button = wx.Button(self, label=_("Previous line"))
        self.read_line_button = wx.Button(self, label=_("Read line"))
        self.next_line_button = wx.Button(self, label=_("Next line"))
        self.read_all_button = wx.Button(self, label=_("Read all"))
        self.back_button = wx.Button(self, label=_("Back"))
        for button in (self.previous_line_button, self.read_line_button, self.next_line_button, self.read_all_button, self.back_button):
            buttons.Add(button, 0, wx.ALL, 4)
        sizer.Add(buttons, 0, wx.ALIGN_CENTER)
        self.SetSizer(sizer)

        self.previous_line_button.Bind(wx.EVT_BUTTON, lambda event: self.move_line(-1))
        self.read_line_button.Bind(wx.EVT_BUTTON, lambda event: self.read_current_line())
        self.next_line_button.Bind(wx.EVT_BUTTON, lambda event: self.move_line(1))
        self.read_all_button.Bind(wx.EVT_BUTTON, lambda event: self.read_all())
        self.back_button.Bind(wx.EVT_BUTTON, lambda event: self.go_back())
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)
        self.details.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        self.update_line(announce=True)

    def update_line(self, announce=False):
        line = self.lines[self.current_line] if self.lines else _("No details.")
        label = _("{position} of {count}: {line}").format(
            position=self.current_line + 1,
            count=len(self.lines),
            line=line,
        )
        self.line_label.SetLabel(label)
        if announce:
            utils.output(label)

    def move_line(self, delta):
        if not self.lines:
            return
        self.current_line = (self.current_line + delta) % len(self.lines)
        self.update_line(announce=True)
        self.details.SetFocus()

    def read_current_line(self):
        self.update_line(announce=True)

    def read_all(self):
        utils.output(self.detail_text)

    def go_back(self):
        utils.get_ui_stack().pop_ui()

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_UP:
            self.move_line(-1)
            return
        if key == wx.WXK_DOWN:
            self.move_line(1)
            return
        if key == wx.WXK_HOME:
            self.current_line = 0
            self.update_line(announce=True)
            return
        if key == wx.WXK_END:
            self.current_line = len(self.lines) - 1
            self.update_line(announce=True)
            return
        if key in (wx.WXK_RETURN, wx.WXK_SPACE):
            self.read_all()
            return
        if key == wx.WXK_ESCAPE:
            self.go_back()
            return
        if key == wx.WXK_F1:
            utils.output(_("Card details. Use up and down to read line by line, Home and End to jump, Space or Enter to read everything, and Escape to return to results."))
            return
        event.Skip()


def _search_cards(name_query="", description_query="", type_query="", attribute_query="", race_query="", limit=SEARCH_LIMIT):
    db = variables.LANGUAGE_HANDLER.primary_database
    translations = _get_card_translations()
    if translations:
        return _search_cards_with_translations(
            db,
            translations,
            name_query,
            description_query,
            type_query,
            attribute_query,
            race_query,
            limit,
        )
    sql = [
        "SELECT texts.id, texts.name",
        "FROM texts JOIN datas ON texts.id = datas.id",
        "WHERE 1=1",
    ]
    params = []
    if name_query:
        sql.append("AND texts.name LIKE ? COLLATE NOCASE")
        params.append(f"%{name_query}%")
    if description_query:
        sql.append("AND texts.desc LIKE ? COLLATE NOCASE")
        params.append(f"%{description_query}%")
    type_mask = _resolve_filter(type_query, TYPE_FILTERS, _("Unknown card type '{value}'"))
    if type_mask:
        sql.append("AND (datas.type & ?) != 0")
        params.append(int(type_mask))
    attribute_mask = _resolve_filter(attribute_query, ATTRIBUTE_FILTERS, _("Unknown attribute '{value}'"))
    if attribute_mask:
        sql.append("AND (datas.attribute & ?) != 0")
        params.append(int(attribute_mask))
    race_mask = _resolve_filter(race_query, RACE_FILTERS, _("Unknown race '{value}'"))
    if race_mask:
        sql.append("AND (datas.race & ?) != 0")
        params.append(int(race_mask))
    sql.append("ORDER BY texts.name LIMIT ?")
    params.append(limit)
    rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    return [_translated_result_row(row[0], row[1]) for row in rows]


def _search_cards_with_translations(db, translations, name_query="", description_query="", type_query="", attribute_query="", race_query="", limit=SEARCH_LIMIT):
    sql = [
        "SELECT texts.id, texts.name, texts.desc",
        "FROM texts JOIN datas ON texts.id = datas.id",
        "WHERE 1=1",
    ]
    params = []
    type_mask = _resolve_filter(type_query, TYPE_FILTERS, _("Unknown card type '{value}'"))
    if type_mask:
        sql.append("AND (datas.type & ?) != 0")
        params.append(int(type_mask))
    attribute_mask = _resolve_filter(attribute_query, ATTRIBUTE_FILTERS, _("Unknown attribute '{value}'"))
    if attribute_mask:
        sql.append("AND (datas.attribute & ?) != 0")
        params.append(int(attribute_mask))
    race_mask = _resolve_filter(race_query, RACE_FILTERS, _("Unknown race '{value}'"))
    if race_mask:
        sql.append("AND (datas.race & ?) != 0")
        params.append(int(race_mask))
    sql.append("ORDER BY texts.name")

    name_query = (name_query or "").casefold()
    description_query = (description_query or "").casefold()
    rows = []
    for row in db.execute(" ".join(sql), tuple(params)).fetchall():
        code = int(row[0])
        translation = translations.get(code) or {}
        display_name = translation.get("name") or row[1]
        display_desc = translation.get("desc") or row[2]
        if name_query and name_query not in display_name.casefold():
            continue
        if description_query and description_query not in display_desc.casefold():
            continue
        rows.append((code, display_name))
    rows.sort(key=lambda item: item[1].casefold())
    return rows[:limit]


def _get_card_translations():
    get_translations = getattr(variables.LANGUAGE_HANDLER, "get_card_translations", None)
    if callable(get_translations):
        translations = get_translations()
        if isinstance(translations, dict):
            return translations
    return {}


def _translated_result_row(code, fallback_name):
    translation = getattr(variables.LANGUAGE_HANDLER, "get_card_translation", lambda _code: None)(code)
    if isinstance(translation, dict) and translation.get("name"):
        return (code, translation["name"])
    return (code, fallback_name)


def _card_from_result_row(row):
    return (int(row[0]), row[1])


def _format_result_label(code, name):
    return _("{name}, {summary}").format(name=name, summary=_format_card_summary(code))


def _resolve_filter(value, mapping, error_template):
    value = (value or "").strip().lower()
    if not value:
        return None
    if value not in mapping:
        raise ValueError(error_template.format(value=value))
    return mapping[value]


def _format_card_summary(code):
    try:
        card = Card(code)
    except Exception:
        logger.exception("Unable to load card %s", code)
        return _("unknown card")
    parts = []
    if card.type & card_constants.TYPE.MONSTER:
        parts.append(_("monster"))
        if card.type & card_constants.TYPE.EXTRA:
            parts.append(_("extra deck"))
        if card.type & card_constants.TYPE.PENDULUM:
            parts.append(_("pendulum"))
        if card.type & card_constants.TYPE.LINK:
            parts.append(_("link"))
    elif card.type & card_constants.TYPE.SPELL:
        parts.append(_("spell"))
    elif card.type & card_constants.TYPE.TRAP:
        parts.append(_("trap"))
    if card.type & card_constants.TYPE.MONSTER:
        parts.append(_("ATK {atk} DEF {defense}").format(atk=card.attack, defense=card.defense))
    return ", ".join(parts) if parts else _("unknown type")


def read_card_detail(code):
    utils.output(_get_card_detail_text(code))


def _get_card_detail_text(code):
    return _("{card}").format(card=str(Card(code)))


def _split_card_detail_lines(detail_text):
    lines = []
    for raw_line in detail_text.splitlines():
        line = raw_line.strip()
        if line:
            lines.append(line)
    return lines or [_("No details.")]
