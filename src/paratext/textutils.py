"""Small helpers for colors and tkinter Text-widget indices/tags."""

from __future__ import annotations


def str_not(string: str) -> str:
    """Negate a boolean stored as a string ('True' <-> 'False').

    :param string: either 'True' or 'False'
    :return: 'False' if string is 'True', otherwise 'True'
    """
    return str(string != "True")


def make_darker(hex_color: str, dark_fac: float = 2) -> str:
    """Darken a ``#RRGGBB`` color by dividing each channel by ``dark_fac``.

    :param hex_color: hex color code as a string (#RRGGBB, any case)
    :param dark_fac: factor to divide each color channel by (default 2)
    :return: new ``#rrggbb`` color string (always 6 zero-padded hex digits)
    """
    if not isinstance(hex_color, str) or len(hex_color) != 7 or hex_color[0] != "#":
        raise ValueError(f"Expected a '#RRGGBB' color string, got {hex_color!r}")
    channels = [short_hex_to_dec(hex_color[i : i + 2]) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(c // dark_fac):02x}" for c in channels)


def get_short_hex(num: float) -> str:
    """Convert a number to hex without the '0x' prefix (no zero padding).

    :param num: number in base 10 (floored to an int)
    :return: the number in base 16, e.g. 255 -> 'ff'
    """
    return format(int(num // 1), "x")


def short_hex_to_dec(short_hex: str) -> int:
    """Convert a hex string (no '0x' prefix, any case) to an int."""
    return int(short_hex, 16)


def char_idx_to_ints(char_idx: str) -> tuple[int, int]:
    """Split a tkinter 'line.col' index string into (line, col) ints."""
    line, col = str(char_idx).split(".")
    return int(line), int(col)


def ints_to_char_idx(line_idx: int, col_idx: int) -> str:
    """Join line and column ints into a tkinter 'line.col' index string."""
    return f"{line_idx}.{col_idx}"


def add_to_char_idx(char_idx: str, mod_int: int, add: bool = True) -> str:
    """Shift the column of a 'line.col' index (never wraps to another line).

    Prefer tkinter index arithmetic (``widget.index(f"{idx}+{n}c")``) when a
    widget is available; it handles line wrapping.
    """
    line_idx, col_idx = char_idx_to_ints(char_idx)
    return ints_to_char_idx(line_idx, col_idx + mod_int if add else col_idx - mod_int)


def del_fn(widg) -> None:
    """Destroy a widget if it exists (``None`` is ignored)."""
    if widg is not None:
        widg.destroy()


def return_matches(twidget, pattern: str) -> list[str]:
    """Find every non-overlapping occurrence of ``pattern`` in a Text widget.

    :param twidget: tkinter Text widget to search
    :param pattern: exact (case-sensitive) text to search for
    :return: list of 'line.col' start indices
    """
    if not pattern:
        return []
    results = []
    start = "1.0"
    while True:
        found = twidget.search(pattern, start, stopindex="end")
        if not found:
            return results
        results.append(found)
        start = twidget.index(f"{found}+{len(pattern)}c")


def get_text_by_tagname(twidget, tagname: str) -> str:
    """Return the text under the first range tagged ``tagname``."""
    bounds = twidget.tag_ranges(tagname)
    if not bounds:
        raise KeyError(f"No text is tagged {tagname!r}")
    return twidget.get(bounds[0], bounds[1])


def replace_tagged_text(twidget, tagname: str, newtext: str) -> None:
    """Replace the text under ``tagname`` while keeping every tag on it.

    The new text is inserted after the old range with the same tags the old
    text started with, then the old range is deleted.  Does nothing if the
    tag is not present in the widget.
    """
    bounds = twidget.tag_ranges(tagname)
    if not bounds:
        return
    start, end = bounds[0], bounds[1]
    tags = tuple(t for t in twidget.tag_names(start) if t != "sel")
    twidget.insert(end, newtext, tags)
    twidget.delete(start, end)


def append_no_dup(item, items: list) -> None:
    """Append ``item`` to ``items`` unless it is already present."""
    if item not in items:
        items.append(item)
