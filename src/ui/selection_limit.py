"""Keep a group of checkboxes within the number of cards the duel will accept.

A prompt that allows one card used to let the player tick as many as they liked
and only complain once the answer had been sent, which the core rejects and
re-asks. Ticking past the limit now quietly releases the oldest choice instead,
so the answer is always one the duel can take.
"""

import logging

import wx

from core import speech
from core import utils
from core.i18n import _

logger = logging.getLogger(__name__)


def _is_checked(checkbox) -> bool:
    for method in ("IsChecked", "GetValue"):
        getter = getattr(checkbox, method, None)
        if getter is None:
            continue
        try:
            return bool(getter())
        except Exception:
            continue
    return False


def _label_of(checkbox, fallback="") -> str:
    for method in ("GetLabel", "GetName"):
        getter = getattr(checkbox, method, None)
        if getter is None:
            continue
        try:
            label = getter()
        except Exception:
            continue
        if label:
            return str(label)
    return fallback


def _announce(text):
    utils.output(text, priority=speech.Priority.CRITICAL)


class SelectionLimiter:
    """Holds at most ``maximum`` checkboxes ticked, oldest released first."""

    def __init__(self, maximum, announce=None):
        self.maximum = maximum if isinstance(maximum, int) and maximum > 0 else 0
        self._announce = announce if announce is not None else _announce
        self._order: list = []
        self._labels: dict[int, str] = {}

    def add(self, checkbox, label=""):
        """Watch a checkbox. Binding may fail outside a running app; the limit
        still applies, because on_toggle can be called directly."""
        if label:
            self._labels[id(checkbox)] = label
        try:
            checkbox.Bind(wx.EVT_CHECKBOX, lambda event, box=checkbox: self.on_toggle(box))
        except Exception:
            logger.debug("Could not bind a checkbox for selection limiting", exc_info=True)
        if _is_checked(checkbox):
            self.on_toggle(checkbox)
        return checkbox

    def selected(self) -> list:
        return list(self._order)

    def on_toggle(self, checkbox):
        """Reconcile the group after one checkbox changed."""
        if _is_checked(checkbox):
            if checkbox not in self._order:
                self._order.append(checkbox)
        else:
            if checkbox in self._order:
                self._order.remove(checkbox)
            return

        if not self.maximum:
            return
        while len(self._order) > self.maximum:
            released = self._order.pop(0)
            self._release(released)

    def _release(self, checkbox):
        try:
            checkbox.SetValue(False)
        except Exception:
            logger.debug("Could not untick a checkbox", exc_info=True)
            return
        name = self._labels.get(id(checkbox)) or _label_of(checkbox, _("a card"))
        self._announce(
            _("{name} unchecked: you may select {max} at a time.").format(
                name=name, max=self.maximum
            )
        )


def limit_checkboxes(checkboxes, maximum, labels=None, announce=None) -> SelectionLimiter:
    """Convenience: limit a list of checkboxes in one call."""
    limiter = SelectionLimiter(maximum, announce=announce)
    for index, checkbox in enumerate(checkboxes):
        label = labels[index] if labels and index < len(labels) else ""
        limiter.add(checkbox, label=label)
    return limiter
