import logging


from core import utils
from core.i18n import _
from game.card.card import Card
from game.edo import structs
from ui import match_ui
from ui.base_ui import VerticalMenu

logger = logging.getLogger(__name__)


def show_side_deck_ui(client):
    """Show the side decking interface for match mode between games."""
    if not hasattr(client.memory, 'deck') or not client.memory.deck:
        utils.output(_("No deck loaded. Cannot side deck."))
        return
    parsed_deck = client.memory.parsed_deck
    main_cards = list(parsed_deck.cards)
    side_cards = list(parsed_deck.side)
    _show_side_menu(client, main_cards, side_cards, [], [])


def _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main):
    menu = VerticalMenu(_("Side Decking"))
    if match_ui.is_match(client):
        menu.append_item(match_ui.score_text(client))
    menu.append_item(_("Side decking: swap cards between your main/extra deck and side deck."))
    menu.append_item(_("Swapped: {out} out, {in_} in").format(out=len(moved_to_side), in_=len(moved_to_main)))
    menu.append_item(_("Move card from main deck to side"), lambda: _pick_from_main(client, main_cards, side_cards, moved_to_side, moved_to_main))
    menu.append_item(_("Move card from side to main deck"), lambda: _pick_from_side(client, main_cards, side_cards, moved_to_side, moved_to_main))
    menu.append_item(_("View current swaps"), lambda: _view_swaps(client, main_cards, side_cards, moved_to_side, moved_to_main))
    menu.append_item(_("Done — submit deck"), lambda: _submit_side_deck(client, main_cards, side_cards))
    utils.get_ui_stack().push_ui(menu)


@utils.ui_function
def _pick_from_main(client, main_cards, side_cards, moved_to_side, moved_to_main):
    menu = VerticalMenu(_("Select card to move to side deck"))
    seen = {}
    for code in main_cards:
        if code in seen:
            seen[code] += 1
        else:
            seen[code] = 1
    for code, count in seen.items():
        card = Card(code)
        label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else card.get_name()
        menu.append_item(str(label), lambda c=code: _do_move_to_side(client, main_cards, side_cards, moved_to_side, moved_to_main, c))
    menu.append_cancel_item(_("Back"), lambda: _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main))
    return menu


@utils.ui_function
def _pick_from_side(client, main_cards, side_cards, moved_to_side, moved_to_main):
    if not side_cards:
        utils.output(_("Side deck is empty."))
        _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main)
        return
    menu = VerticalMenu(_("Select card to move to main deck"))
    seen = {}
    for code in side_cards:
        if code in seen:
            seen[code] += 1
        else:
            seen[code] = 1
    for code, count in seen.items():
        card = Card(code)
        label = _("{name} x{count}").format(name=card.get_name(), count=count) if count > 1 else card.get_name()
        menu.append_item(str(label), lambda c=code: _do_move_to_main(client, main_cards, side_cards, moved_to_side, moved_to_main, c))
    menu.append_cancel_item(_("Back"), lambda: _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main))
    return menu


def _do_move_to_side(client, main_cards, side_cards, moved_to_side, moved_to_main, code):
    utils.get_ui_stack().pop_ui()
    main_cards.remove(code)
    side_cards.append(code)
    moved_to_side.append(code)
    card = Card(code)
    utils.output(_("{name} moved to side deck.").format(name=card.get_name()))
    _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main)


def _do_move_to_main(client, main_cards, side_cards, moved_to_side, moved_to_main, code):
    utils.get_ui_stack().pop_ui()
    side_cards.remove(code)
    main_cards.append(code)
    moved_to_main.append(code)
    card = Card(code)
    utils.output(_("{name} moved to main deck.").format(name=card.get_name()))
    _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main)


@utils.ui_function
def _view_swaps(client, main_cards, side_cards, moved_to_side, moved_to_main):
    menu = VerticalMenu(_("Current swaps"))
    if not moved_to_side and not moved_to_main:
        menu.append_item(_("No swaps made yet."))
    for code in moved_to_side:
        card = Card(code)
        menu.append_item(_("{name} → side").format(name=card.get_name()))
    for code in moved_to_main:
        card = Card(code)
        menu.append_item(_("{name} → main").format(name=card.get_name()))
    menu.append_cancel_item(_("Back"), lambda: _show_side_menu(client, main_cards, side_cards, moved_to_side, moved_to_main))
    return menu


def _submit_side_deck(client, main_cards, side_cards):
    utils.get_ui_stack().pop_ui()
    deck = structs.Deck()
    deck.set_main_deck(main_cards)
    deck.set_side_deck(side_cards)
    client.send(structs.ClientIdType.UPDATE_DECK, deck)
    client.memory.deck = deck
    utils.output(_("Side deck submitted. Waiting for next game."))
