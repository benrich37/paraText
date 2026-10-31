"""Helpers for driving tkinter widgets in tests (synthetic mouse events)."""

from __future__ import annotations


def _right_button(ex) -> int:
    return 2 if ex.tk.call("tk", "windowingsystem") == "aqua" else 3


def _click(ex, coords, button: int, modifier: str = "") -> None:
    ex.event_generate("<Motion>", x=coords[0], y=coords[1])
    ex.event_generate(f"<{modifier}Button-{button}>", x=coords[0], y=coords[1])
    ex.event_generate(f"<{modifier}ButtonRelease-{button}>", x=coords[0], y=coords[1])


def right_click_coord(ex, coords) -> None:
    _click(ex, coords, _right_button(ex))


def left_click_coord(ex, coords) -> None:
    _click(ex, coords, 1)


def shift_right_click_coord(ex, coords) -> None:
    _click(ex, coords, _right_button(ex), "Shift-")


def shift_left_click_coord(ex, coords) -> None:
    _click(ex, coords, 1, "Shift-")


def click_char(ex, char_idx, click_fn) -> None:
    """Click on the character at ``char_idx`` of a Text widget with ``click_fn``."""
    click_fn(ex, ex.bbox(char_idx))
