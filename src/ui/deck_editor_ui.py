"""Deck editor.

Four accessibility problems shaped this version:

* You could not read a card before adding it. Every list of cards here is a
  ``CardChoiceMenu``, so Space reads the card you are sitting on.
* The editor had its own ``LIKE`` query that ignored the translation catalogue,
  so a French player searched English names and then saw French ones on the next
  screen. Searching now goes through ``card_search_ui.search_cards``, the same
  engine the Card Search feature uses, with its filters and translations.
* Adding or removing one copy bounced you back to the deck menu, so three
  copies meant walking the whole path three times. Add and remove now leave you
  where you were, with the new count announced.
* The copy limit was hard coded to three and the save refused anything under
  forty cards. The limit now follows the banlist you pick, and a deck that is
  not legal yet saves anyway as a draft, with the problems read out.
"""

import logging
from collections import OrderedDict

import wx

from core import utils
from core import variables
from core.i18n import _
from game.card.card import Card
from game.card import card_constants
from game.card.ydke import Deck
from game.edo import banlists
from ui import card_search_ui
from ui.base_ui import VerticalMenu, InputUI
from ui.card_details_ui import CardChoiceMenu, show_card_details

logger = logging.getLogger(__name__)

MAX_MAIN_DECK = 60
MIN_MAIN_DECK = 40
MAX_EXTRA_DECK = 15
MAX_SIDE_DECK = 15
DEFAULT_MAX_COPIES = 3


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
        menu.append_item(str(f.stem), lambda f=f: load_and_edit(f, return_to))
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
    menu.set_help_text(_("Arrow keys to move, Enter to choose. In any card list, Space reads the card under the cursor."))
    menu.append_item(_("Main deck: {main} cards, Extra deck: {extra} cards, Side: {side} cards").format(main=main_only, extra=extra_count, side=side_count))
    menu.append_item(_("Status: {status}").format(status=_deck_status_text(deck_data)))
    menu.append_item(_("Add card"), lambda: search_card_to_add(name, deck_data, return_to))
    menu.append_item(_("Remove card from main/extra"), lambda: remove_card_menu(name, deck_data, "main", return_to))
    menu.append_item(_("Remove card from side"), lambda: remove_card_menu(name, deck_data, "side", return_to))
    menu.append_item(_("View main deck"), lambda: view_deck_list(name, deck_data, "main", return_to))
    menu.append_item(_("View side deck"), lambda: view_deck_list(name, deck_data, "side", return_to))
    menu.append_item(_("Banlist for copy limits: {banlist}").format(banlist=_banlist_label(deck_data)), lambda: choose_working_banlist(name, deck_data, return_to))
    menu.append_item(_("Check against banlist"), lambda: check_deck_against_banlist(name, deck_data, return_to))
    menu.append_item(_("Export deck string"), lambda: export_deck_string(name, deck_data, return_to))
    menu.append_item(_("Save deck"), lambda: save_deck(name, deck_data, return_to))
    menu.append_item(_("Back without saving"), lambda: deck_editor_main_menu(return_to))
    return menu


# --------------------------------------------------------------------------
# Banlist aware copy limits
# --------------------------------------------------------------------------

def _banlist_label(deck_data):
    return deck_data.get("banlist") or _("none, three copies allowed")


def _active_banlist(deck_data):
    """The banlist chosen for this editing session, if any."""
    banlist_name = deck_data.get("banlist")
    if not banlist_name:
        return None
    try:
        return banlists.BanlistManager().get_banlist_by_name(banlist_name)
    except Exception:
        logger.exception("Could not load banlist %s", banlist_name)
        return None


def _max_copies(deck_data, code):
    banlist = _active_banlist(deck_data)
    if banlist is None:
        return DEFAULT_MAX_COPIES
    try:
        return int(banlist.get_limit(code))
    except Exception:
        logger.exception("Could not read the limit for card %s", code)
        return DEFAULT_MAX_COPIES


def _copies_in_deck(deck_data, code):
    return deck_data["main"].count(code) + deck_data["side"].count(code)


def _copy_limit_message(deck_data, code, limit):
    card = Card(code)
    if limit <= 0:
        return _("{name} is forbidden by this banlist.").format(name=card.get_name())
    if limit == 1:
        return _("{name} is limited to one copy.").format(name=card.get_name())
    return _("Already have {limit} copies of {name}.").format(limit=limit, name=card.get_name())


@utils.ui_function
def choose_working_banlist(name, deck_data, return_to):
    menu = VerticalMenu(_("Banlist used for copy limits"))
    menu.append_item(_("No banlist, allow three copies"), lambda: _set_working_banlist(name, deck_data, None, return_to))
    try:
        banlist_names = banlists.BanlistManager().get_banlist_names()
    except Exception:
        logger.exception("Could not list banlists")
        banlist_names = []
    if not banlist_names:
        menu.append_item(_("No banlists are installed."))
    for banlist_name in banlist_names:
        menu.append_item(str(banlist_name), lambda banlist_name=banlist_name: _set_working_banlist(name, deck_data, banlist_name, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def _set_working_banlist(name, deck_data, banlist_name, return_to):
    deck_data["banlist"] = banlist_name
    if banlist_name:
        utils.output(_("Copy limits now follow {banlist}.").format(banlist=banlist_name))
    else:
        utils.output(_("Copy limits back to three per card."))
    edit_deck(name, deck_data, return_to)


# --------------------------------------------------------------------------
# Adding cards
# --------------------------------------------------------------------------

@utils.ui_function
def search_card_to_add(name, deck_data, return_to, query=None):
    """Search for a card to add, reusing the Card Search engine.

    ``query`` is passed back in when returning from an add, so that adding
    several copies does not mean typing the search again.
    """
    if query is None:
        search_input = InputUI(_("Search card by name"))
        query = search_input.show()
    if not query:
        edit_deck(name, deck_data, return_to)
        return
    try:
        rows = card_search_ui.search_cards(name_query=query)
    except ValueError as exc:
        utils.output(str(exc))
        edit_deck(name, deck_data, return_to)
        return
    if not rows:
        utils.output(_("No cards found for '{query}'.").format(query=query))
        edit_deck(name, deck_data, return_to)
        return
    if len(rows) >= card_search_ui.SEARCH_LIMIT:
        utils.output(_("{count} results, showing the first {limit}. Narrow the search for more.").format(count=len(rows), limit=card_search_ui.SEARCH_LIMIT))
    else:
        utils.output(_("{count} result(s).").format(count=len(rows)))
    menu = CardChoiceMenu(_("Search results for '{query}'").format(query=query))
    menu.set_help_text(_("Enter chooses where to add the card. Space reads the card first."))
    for code, card_name in rows:
        menu.append_card(code, _result_label(deck_data, code, card_name), lambda c=code: choose_add_destination(name, deck_data, c, return_to, query=query))
    menu.append_item(_("New search"), lambda: search_card_to_add(name, deck_data, return_to))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def _result_label(deck_data, code, card_name):
    """One search result: name, what it is, and how many you already hold."""
    summary = card_search_ui.format_card_summary(code)
    copies = _copies_in_deck(deck_data, code)
    if copies:
        return _("{name}, {summary}, {copies} already in deck").format(name=card_name, summary=summary, copies=copies)
    return _("{name}, {summary}").format(name=card_name, summary=summary)


@utils.ui_function
def choose_add_destination(name, deck_data, code, return_to, query=None):
    card = Card(code)
    back_to_results = (lambda: search_card_to_add(name, deck_data, return_to, query=query)) if query else (lambda: edit_deck(name, deck_data, return_to))
    remaining = _max_copies(deck_data, code) - _copies_in_deck(deck_data, code)
    menu = VerticalMenu(_("Add {name}").format(name=card.get_name()))
    menu.append_item(_("Read card details"), lambda: show_card_details(code))
    menu.append_item(_("Add to main or extra deck"), lambda: add_card_to_deck(name, deck_data, code, return_to, after=back_to_results))
    menu.append_item(_("Add to side deck"), lambda: add_card_to_side(name, deck_data, code, return_to, after=back_to_results))
    if remaining > 1:
        menu.append_item(
            _("Add {count} copies to main or extra deck").format(count=remaining),
            lambda: add_copies_to_deck(name, deck_data, code, remaining, return_to, after=back_to_results),
        )
    menu.append_item(_("Back"), back_to_results)
    return menu


def _room_in_deck(deck_data, code):
    """Why the card cannot go into the main or extra deck, or None if it can."""
    if _is_extra_deck_card(code):
        extra_count = sum(1 for c in deck_data["main"] if _is_extra_deck_card(c))
        if extra_count >= MAX_EXTRA_DECK:
            return _("Extra deck is full ({max} cards).").format(max=MAX_EXTRA_DECK)
    else:
        main_only = sum(1 for c in deck_data["main"] if not _is_extra_deck_card(c))
        if main_only >= MAX_MAIN_DECK:
            return _("Main deck is full ({max} cards).").format(max=MAX_MAIN_DECK)
    limit = _max_copies(deck_data, code)
    if _copies_in_deck(deck_data, code) >= limit:
        return _copy_limit_message(deck_data, code, limit)
    return None


def add_card_to_deck(name, deck_data, code, return_to, after=None):
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    problem = _room_in_deck(deck_data, code)
    if problem:
        utils.output(str(problem))
    else:
        deck_data["main"].append(code)
        utils.output(_("{name} added. {copies} in deck.").format(name=card.get_name(), copies=_copies_in_deck(deck_data, code)))
    _return_after_change(name, deck_data, return_to, after)


def add_copies_to_deck(name, deck_data, code, count, return_to, after=None):
    """Add several copies at once, stopping at the first thing in the way."""
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    added = 0
    problem = None
    for _unused in range(count):
        problem = _room_in_deck(deck_data, code)
        if problem:
            break
        deck_data["main"].append(code)
        added += 1
    if added:
        utils.output(_("{count} copies of {name} added. {copies} in deck.").format(count=added, name=card.get_name(), copies=_copies_in_deck(deck_data, code)))
    if problem:
        utils.output(str(problem))
    _return_after_change(name, deck_data, return_to, after)


def add_card_to_side(name, deck_data, code, return_to, after=None):
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    limit = _max_copies(deck_data, code)
    if len(deck_data["side"]) >= MAX_SIDE_DECK:
        utils.output(_("Side deck is full ({max} cards).").format(max=MAX_SIDE_DECK))
    elif _copies_in_deck(deck_data, code) >= limit:
        utils.output(_copy_limit_message(deck_data, code, limit))
    else:
        deck_data["side"].append(code)
        utils.output(_("{name} added to side deck. {copies} in deck.").format(name=card.get_name(), copies=_copies_in_deck(deck_data, code)))
    _return_after_change(name, deck_data, return_to, after)


def _return_after_change(name, deck_data, return_to, after):
    """Go back where the player was, not all the way out to the deck menu."""
    if after is not None:
        after()
        return
    edit_deck(name, deck_data, return_to)


# --------------------------------------------------------------------------
# Removing and viewing cards
# --------------------------------------------------------------------------

@utils.ui_function
def remove_card_menu(name, deck_data, section, return_to):
    cards = deck_data[section]
    if not cards:
        utils.output(_("No cards in {section}.").format(section=section))
        edit_deck(name, deck_data, return_to)
        return
    back_here = lambda: remove_card_menu(name, deck_data, section, return_to)  # noqa: E731
    menu = CardChoiceMenu(_("Remove card from {section}").format(section=section))
    menu.set_help_text(_("Enter removes one copy and keeps you here. Space reads the card."))
    for code, count in _group_cards_combined(cards).items():
        card = Card(code)
        label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else card.get_name()
        menu.append_card(code, str(label), lambda c=code: _do_remove(name, deck_data, section, c, return_to, after=back_here))
    menu.append_item(_("Back"), lambda: edit_deck(name, deck_data, return_to))
    return menu


def _do_remove(name, deck_data, section, code, return_to, after=None):
    utils.get_ui_stack().pop_ui()
    card = Card(code)
    if code in deck_data[section]:
        deck_data[section].remove(code)
        remaining = deck_data[section].count(code)
        if remaining:
            utils.output(_("{name} removed. {count} left.").format(name=card.get_name(), count=remaining))
        else:
            utils.output(_("{name} removed.").format(name=card.get_name()))
    else:
        utils.output(_("{name} is not in {section}.").format(name=card.get_name(), section=section))
    if after is not None and deck_data[section]:
        after()
        return
    edit_deck(name, deck_data, return_to)


@utils.ui_function
def view_deck_list(name, deck_data, section, return_to):
    cards = deck_data[section]
    if not cards:
        utils.output(_("No cards in {section}.").format(section=section))
        edit_deck(name, deck_data, return_to)
        return
    menu = CardChoiceMenu(_("{section} ({count} cards)").format(section=section.capitalize(), count=len(cards)))
    menu.set_help_text(_("Enter opens the full card text. Space reads it without leaving the list."))
    grouped = _group_cards_by_section(cards)
    for section_name, section_cards in grouped:
        if not section_cards:
            continue
        menu.append_item(_("{section} ({count})").format(section=section_name, count=sum(section_cards.values())))
        for code, count in section_cards.items():
            card = Card(code)
            label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else card.get_name()
            menu.append_card(code, str(label), lambda c=code: show_card_details(c))
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
    utils.output(str(card))


# --------------------------------------------------------------------------
# Banlist check, export and save
# --------------------------------------------------------------------------

@utils.ui_function
def check_deck_against_banlist(name, deck_data, return_to):
    validation_error = _validate_deck_for_save(deck_data)
    if validation_error:
        utils.output(str(validation_error))
    manager = banlists.BanlistManager()
    menu = VerticalMenu(_("Check '{name}' against banlist").format(name=name))
    for banlist_name in manager.get_banlist_names():
        menu.append_item(str(banlist_name), lambda banlist_name=banlist_name: show_banlist_check_result(name, deck_data, banlist_name, return_to))
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
    menu.append_item(_("Use this banlist for copy limits"), lambda: _set_working_banlist(name, deck_data, banlist_name, return_to))
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
    """Always save. An incomplete deck is a draft, not an error.

    Refusing to write anything under forty cards meant losing the work in
    progress on the way out. The problems are read out instead, and the server
    still rejects an illegal deck when a duel actually starts.
    """
    utils.get_ui_stack().pop_ui()
    deck_dir = variables.DECK_DIR
    deck_dir.mkdir(parents=True, exist_ok=True)
    deck = Deck(deck_data["main"], deck_data["side"])
    deck_file = deck_dir / f"{utils.sanitize_filename(name)}.json"
    with open(deck_file, "w") as f:
        f.write(deck.to_json())
    validation_error = _validate_deck_for_save(deck_data)
    if validation_error:
        utils.output(_("Deck '{name}' saved as a draft. {problem}").format(name=name, problem=validation_error))
    else:
        utils.output(_("Deck '{name}' saved.").format(name=name))
    deck_editor_main_menu(return_to)


def _deck_status_text(deck_data):
    problem = _validate_deck_for_save(deck_data)
    if problem:
        return str(problem)
    return _("ready to play")


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
        if all_cards.count(code) > DEFAULT_MAX_COPIES:
            card = Card(code)
            return _("Deck cannot contain more than 3 copies of {name}.").format(name=card.get_name())
    return None


def _is_extra_deck_card(code):
    try:
        card = Card(code)
        return bool(card.type & card_constants.TYPE.EXTRA)
    except Exception:
        return False
