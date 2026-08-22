import json
import logging
from pathlib import Path
from collections import OrderedDict

import wx

from core import utils
from core import variables
from core.i18n import _
from game.card.card import Card
from game.card import card_constants
from game.card.ydke import Deck
from game.edo import banlists
from ui.base_ui import VerticalMenu, InputUI

logger = logging.getLogger(__name__)

MAX_MAIN_DECK = 60
MIN_MAIN_DECK = 40
MAX_EXTRA_DECK = 15
MAX_SIDE_DECK = 15


@utils.ui_function
def deck_editor_main_menu(return_to=None):
    if not return_to:
        from ui.main_ui import main_menu_view
        return_to = main_menu_view
    menu = VerticalMenu(_("Deck Editor"))
    menu.set_help_text(_("Create and edit decks. Use arrow keys to navigate."))
    menu.append_item(_("New Deck"), lambda: new_deck(return_to))
    menu.append_item(_("Edit Existing Deck"), lambda: pick_deck_to_edit(return_to))
    menu.append_item(_("Back"), return_to)
    return menu


@utils.ui_function
def new_deck(return_to):
    name_input = InputUI(_("Deck name"))
    name = name_input.show()
    if not name:
        deck_editor_main_menu(return_to)
        return
    deck_data = {"main": [], "side": []}
    edit_deck(name, deck_data, return_to)


@utils.ui_function
def pick_deck_to_edit(return_to):
    deck_dir = variables.DECK_DIR
    if not deck_dir.exists():
        deck_dir.mkdir(parents=True, exist_ok=True)
    files = [f for f in deck_dir.iterdir() if f.is_file() and f.suffix.lower() in (".json", ".ydke")]
    if not files:
        utils.output(_("No decks found."))
        deck_editor_main_menu(return_to)
        return
    menu = VerticalMenu(_("Select deck to edit"))
    for f in files:
        menu.append_item(_("{name}").format(name=f.stem), lambda f=f: load_and_edit(f, return_to))
    menu.append_item(_("Back"), lambda: deck_editor_main_menu(return_to))
    return menu


def load_and_edit(deck_file, return_to):
    with open(deck_file, "r") as f:
        if deck_file.suffix == ".ydke":
            parsed = Deck.from_ydke(f.read())
        else:
            parsed = Deck.from_json(f.read())
    deck_data = {"main": list(parsed.cards), "side": list(parsed.side)}
    edit_deck(deck_file.stem, deck_data, return_to)


@utils.ui_function
def edit_deck(name, deck_data, return_to):
    main_count = len(deck_data["main"])
    extra_count = sum(1 for c in deck_data["main"] if _is_extra_deck_card(c))
    main_only = main_count - extra_count
    side_count = len(deck_data["side"])
    menu = VerticalMenu(_("Editing: {name}").format(name=name))
    menu.append_item(_("Main deck: {main} cards, Extra deck: {extra} cards, Side: {side} cards").format(main=main_only, extra=extra_count, side=side_count))
    menu.append_item(_("Add card"), lambda: search_card_to_add(name, deck_data, return_to))
    menu.append_item(_("Remove card from main/extra"), lambda: remove_card_menu(name, deck_data, "main", return_to))
    menu.append_item(_("Remove card from side"), lambda: remove_card_menu(name, deck_data, "side", return_to))
    menu.append_item(_("View main deck"), lambda: view_deck_list(name, deck_data, "main", return_to))
    menu.append_item(_("View side deck"), lambda: view_deck_list(name, deck_data, "side", return_to))
    menu.append_item(_("Check against banlist"), lambda: check_deck_against_banlist(name, deck_data, return_to))
    menu.append_item(_("Export deck string"), lambda: export_deck_string(name, deck_data, return_to))
    menu.append_item(_("Save deck"), lambda: save_deck(name, deck_data, return_to))
    menu.append_item(_("Back without saving"), lambda: deck_editor_main_menu(return_to))
    return menu


@utils.ui_function
def search_card_to_add(name, deck_data, return_to):
    search_input = InputUI(_("Search card by name"))
    query = search_input.show()
    if not query:
        edit_deck(name, deck_data, return_to)
        return
    db = variables.LANGUAGE_HANDLER.primary_database
    rows = db.execute("SELECT id, name FROM texts WHERE name LIKE ? COLLATE NOCASE LIMIT 50", (f"%{query}%",)).fetchall()
    if not rows:
        utils.output(_("No cards found for '{query}'.").format(query=query))
        edit_deck(name, deck_data, return_to)
        return
    menu = VerticalMenu(_("Search results for '{query}'").format(query=query))
    for row in rows:
        code = row[0]
        card_name = row[1]
        menu.append_item(_("{name}").format(name=card_name), lambda c=code: choose_add_destination(name, deck_data, c, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


@utils.ui_function
def choose_add_destination(name, deck_data, code, return_to):
    card = Card(code)
    menu = VerticalMenu(_("Add {name}").format(name=card.get_name()))
    menu.append_item(_("Add to main or extra deck"), lambda: add_card_to_deck(name, deck_data, code, return_to))
    menu.append_item(_("Add to side deck"), lambda: add_card_to_side(name, deck_data, code, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def add_card_to_deck(name, deck_data, code, return_to):
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    if _is_extra_deck_card(code):
        extra_count = sum(1 for c in deck_data["main"] if _is_extra_deck_card(c))
        if extra_count >= MAX_EXTRA_DECK:
            utils.output(_("Extra deck is full ({max} cards).").format(max=MAX_EXTRA_DECK))
            edit_deck(name, deck_data, return_to)
            return
    else:
        main_only = sum(1 for c in deck_data["main"] if not _is_extra_deck_card(c))
        if main_only >= MAX_MAIN_DECK:
            utils.output(_("Main deck is full ({max} cards).").format(max=MAX_MAIN_DECK))
            edit_deck(name, deck_data, return_to)
            return
    copies = deck_data["main"].count(code) + deck_data["side"].count(code)
    if copies >= 3:
        utils.output(_("Already have 3 copies of {name}.").format(name=card.get_name()))
        edit_deck(name, deck_data, return_to)
        return
    deck_data["main"].append(code)
    utils.output(_("{name} added to deck.").format(name=card.get_name()))
    edit_deck(name, deck_data, return_to)


def add_card_to_side(name, deck_data, code, return_to):
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    if len(deck_data["side"]) >= MAX_SIDE_DECK:
        utils.output(_("Side deck is full ({max} cards).").format(max=MAX_SIDE_DECK))
    else:
        copies = deck_data["main"].count(code) + deck_data["side"].count(code)
        if copies >= 3:
            utils.output(_("Already have 3 copies of {name}.").format(name=card.get_name()))
        else:
            deck_data["side"].append(code)
            utils.output(_("{name} added to side deck.").format(name=card.get_name()))
    edit_deck(name, deck_data, return_to)


@utils.ui_function
def remove_card_menu(name, deck_data, section, return_to):
    cards = deck_data[section]
    if not cards:
        utils.output(_("No cards in {section}.").format(section=section))
        edit_deck(name, deck_data, return_to)
        return
    menu = VerticalMenu(_("Remove card from {section}").format(section=section))
    for code, count in _group_cards_combined(cards).items():
        card = Card(code)
        label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else _("{name}").format(name=card.get_name())
        menu.append_item(_("{label}").format(label=label), lambda c=code: _do_remove(name, deck_data, section, c, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def _do_remove(name, deck_data, section, code, return_to):
    utils.get_ui_stack().pop_ui()
    deck_data[section].remove(code)
    card = Card(code)
    utils.output(_("{name} removed.").format(name=card.get_name()))
    edit_deck(name, deck_data, return_to)


@utils.ui_function
def view_deck_list(name, deck_data, section, return_to):
    cards = deck_data[section]
    if not cards:
        utils.output(_("No cards in {section}.").format(section=section))
        edit_deck(name, deck_data, return_to)
        return
    menu = VerticalMenu(_("{section} ({count} cards)").format(section=section.capitalize(), count=len(cards)))
    grouped = _group_cards_by_section(cards)
    for section_name, section_cards in grouped:
        if not section_cards:
            continue
        menu.append_item(_("{section} ({count})").format(section=section_name, count=sum(section_cards.values())))
        for code, count in section_cards.items():
            card = Card(code)
            label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else _("{name}").format(name=card.get_name())
            menu.append_item(_("{label}").format(label=label), lambda c=code: _read_card_detail(c))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def _group_cards_by_section(cards):
    groups = [
        (_("Monsters"), []),
        (_("Spells"), []),
        (_("Traps"), []),
        (_("Extra deck"), []),
        (_("Other"), []),
    ]
    for code in cards:
        card = Card(code)
        if card.type & card_constants.TYPE.EXTRA:
            groups[3][1].append(code)
        elif card.type & card_constants.TYPE.MONSTER:
            groups[0][1].append(code)
        elif card.type & card_constants.TYPE.SPELL:
            groups[1][1].append(code)
        elif card.type & card_constants.TYPE.TRAP:
            groups[2][1].append(code)
        else:
            groups[4][1].append(code)
    return [(name, _group_cards(section_cards)) for name, section_cards in groups]


def _group_cards_combined(cards):
    combined = OrderedDict()
    for _section_name, grouped_cards in _group_cards_by_section(cards):
        combined.update(grouped_cards)
    return combined


def _group_cards(cards):
    grouped = {}
    for code in cards:
        grouped[code] = grouped.get(code, 0) + 1
    return OrderedDict(sorted(grouped.items(), key=lambda item: Card(item[0]).get_name().lower()))


def _read_card_detail(code):
    card = Card(code)
    utils.output(_("{card}").format(card=str(card)))


@utils.ui_function
def check_deck_against_banlist(name, deck_data, return_to):
    validation_error = _validate_deck_for_save(deck_data)
    if validation_error:
        utils.output(_("{error}").format(error=validation_error))
    manager = banlists.BanlistManager()
    menu = VerticalMenu(_("Check '{name}' against banlist").format(name=name))
    for banlist_name in manager.get_banlist_names():
        menu.append_item(_("{banlist}").format(banlist=banlist_name), lambda banlist_name=banlist_name: show_banlist_check_result(name, deck_data, banlist_name, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


@utils.ui_function
def show_banlist_check_result(name, deck_data, banlist_name, return_to):
    deck = Deck(deck_data["main"], deck_data["side"])
    selected_banlist = banlists.BanlistManager().get_banlist_by_name(banlist_name)
    is_allowed, reason = selected_banlist.is_deck_allowed(deck)
    menu = VerticalMenu(_("Banlist result"))
    if is_allowed:
        menu.append_item(_("Deck is legal for {banlist}.").format(banlist=banlist_name), None)
    else:
        menu.append_item(_("Deck is not legal for {banlist}.").format(banlist=banlist_name), None)
        for card_code, card_info in reason.items():
            card = Card(card_code)
            menu.append_item(
                _("{card} is limited to {limit} and you have {found}.").format(
                    card=card.get_name(), limit=card_info.limit, found=card_info.found
                ),
                None,
            )
    menu.append_item(_("Back"), lambda: check_deck_against_banlist(name, deck_data, return_to))
    return menu


def export_deck_string(name, deck_data, return_to):
    deck = Deck(deck_data["main"], deck_data["side"])
    wx.TheClipboard.Open()
    wx.TheClipboard.SetData(wx.TextDataObject(deck.to_ydke()))
    wx.TheClipboard.Close()
    utils.output(_("Deck string for '{name}' copied to clipboard.").format(name=name))
    edit_deck(name, deck_data, return_to)


def save_deck(name, deck_data, return_to):
    utils.get_ui_stack().pop_ui()
    validation_error = _validate_deck_for_save(deck_data)
    if validation_error:
        utils.output(_("{error}").format(error=validation_error))
        edit_deck(name, deck_data, return_to)
        return
    deck_dir = variables.DECK_DIR
    deck_dir.mkdir(parents=True, exist_ok=True)
    deck = Deck(deck_data["main"], deck_data["side"])
    deck_file = deck_dir / f"{utils.sanitize_filename(name)}.json"
    with open(deck_file, "w") as f:
        f.write(deck.to_json())
    utils.output(_("Deck '{name}' saved.").format(name=name))
    deck_editor_main_menu(return_to)


def _validate_deck_for_save(deck_data):
    main_only = sum(1 for c in deck_data["main"] if not _is_extra_deck_card(c))
    extra_count = sum(1 for c in deck_data["main"] if _is_extra_deck_card(c))
    side_count = len(deck_data["side"])
    if main_only < MIN_MAIN_DECK:
        return _("Main deck must contain at least {min} cards.").format(min=MIN_MAIN_DECK)
    if main_only > MAX_MAIN_DECK:
        return _("Main deck cannot contain more than {max} cards.").format(max=MAX_MAIN_DECK)
    if extra_count > MAX_EXTRA_DECK:
        return _("Extra deck cannot contain more than {max} cards.").format(max=MAX_EXTRA_DECK)
    if side_count > MAX_SIDE_DECK:
        return _("Side deck cannot contain more than {max} cards.").format(max=MAX_SIDE_DECK)
    all_cards = deck_data["main"] + deck_data["side"]
    for code in set(all_cards):
        if all_cards.count(code) > 3:
            card = Card(code)
            return _("Deck cannot contain more than 3 copies of {name}.").format(name=card.get_name())
    return None


def _is_extra_deck_card(code):
    try:
        card = Card(code)
        return bool(card.type & card_constants.TYPE.EXTRA)
    except Exception:
        return False
