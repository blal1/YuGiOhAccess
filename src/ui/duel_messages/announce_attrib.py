import io
import struct

from core import utils, variables
from core.i18n import _
from game.card import card_constants
from game.edo import structs
from ui.base_ui import VerticalMenu


@utils.duel_message_handler(141)
def msg_announce_attrib(client, data, length):
    data = io.BytesIO(data[1:])
    player = client.read_u8(data)
    count = client.read_u8(data)
    available = client.read_u32(data)
    announce_attrib(client, player, count, available)


def announce_attrib(client, player, count, available):
    options = _available_values(
        available,
        card_constants.ATTRIBUTES_OFFSET,
        card_constants.AMOUNT_ATTRIBUTES,
        _("Attribute {number}"),
    )
    show_announce_value_menu(client, _("Select attribute"), count, options)


def show_announce_value_menu(client, title, count, options):
    if count <= 0:
        count = 1
    if not options:
        utils.output(_("No valid options available."))
        return
    if count == 1:
        menu = VerticalMenu(_("{title}").format(title=title))
        for label, value in options:
            menu.append_item(_("{label}").format(label=label), function=lambda value=value: _send_response(client, value, True))
        utils.get_ui_stack().push_ui(menu)
        return
    menu = VerticalMenu(_("{title}").format(title=title))
    selected = []
    menu.append_item(_("Select {count} values").format(count=count))
    for label, value in options:
        menu.append_item(_("{label}").format(label=label), function=lambda label=label, value=value: _toggle_value(client, menu, selected, count, label, value))
    menu.append_item(_("Finish"), function=lambda: _finish_multi_select(client, selected, count))
    utils.get_ui_stack().push_ui(menu)


def _available_values(available, offset, amount, fallback_template):
    labels = variables.LANGUAGE_HANDLER.strings.get("system", {})
    options = []
    for i in range(amount):
        value = 1 << i
        if available & value:
            label = labels.get(offset + i, fallback_template.format(number=i + 1))
            options.append((label, value))
    return sorted(options, key=lambda item: item[0].lower())


def _toggle_value(client, menu, selected, count, label, value):
    if value in selected:
        selected.remove(value)
        utils.output(_("Unselected {label}.").format(label=label))
        return
    if len(selected) >= count:
        utils.output(_("You already selected {count} values.").format(count=count))
        return
    selected.append(value)
    utils.output(_("Selected {label}.").format(label=label))
    if len(selected) == count:
        _finish_multi_select(client, selected, count)


def _finish_multi_select(client, selected, count):
    if len(selected) != count:
        utils.output(_("Select exactly {count} values.").format(count=count))
        return
    _send_response(client, sum(selected), True)


def _send_response(client, value, pop_last_ui):
    if pop_last_ui:
        utils.get_ui_stack().pop_ui()
    client.send(structs.ClientIdType.RESPONSE, struct.pack("I", value))
