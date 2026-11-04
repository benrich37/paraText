"""Read PDFs with PyMuPDF: page images, words with bounding boxes, and text.

PyMuPDF is not thread-safe, so every access to the underlying document goes
through one lock; callers (engine workers, the GUI's render thread) may use a
``PdfDocument`` from any thread.
"""

from __future__ import annotations

import hashlib
import threading
from functools import cached_property
from pathlib import Path
from typing import NamedTuple

import pymupdf

# Expand typographic ligatures (ﬁ, ﬀ, ...) so words match plain-text terms
_WORD_FLAGS = pymupdf.TEXTFLAGS_WORDS & ~pymupdf.TEXT_PRESERVE_LIGATURES
_TEXT_FLAGS = pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_LIGATURES


class Word(NamedTuple):
    """A word on a page; coordinates are PDF points from the page's top-left."""

    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    block: int
    line: int

    def contains(self, x: float, y: float) -> bool:
        return self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1


class RenderedPage(NamedTuple):
    """Raw RGB pixels of a rendered page."""

    width: int
    height: int
    stride: int
    samples: bytes


class PdfDocument:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._doc = pymupdf.open(self.path)
        self._words: dict[int, list[Word]] = {}
        self._texts: dict[int, str] = {}
        self._sizes: dict[int, tuple[float, float]] = {}

    def close(self) -> None:
        with self._lock:
            self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def page_count(self) -> int:
        with self._lock:
            return self._doc.page_count

    @cached_property
    def sha256(self) -> str:
        digest = hashlib.sha256()
        with open(self.path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @property
    def title(self) -> str:
        with self._lock:
            return (self._doc.metadata or {}).get("title") or self.path.stem

    def page_size(self, page_no: int) -> tuple[float, float]:
        if page_no not in self._sizes:
            with self._lock:
                rect = self._doc[page_no].rect
                self._sizes[page_no] = (rect.width, rect.height)
        return self._sizes[page_no]

    def words(self, page_no: int) -> list[Word]:
        """Words in content-stream order (usually reading order, column by column)."""
        if page_no not in self._words:
            with self._lock:
                raw = self._doc[page_no].get_text("words", flags=_WORD_FLAGS)
                self._words[page_no] = [Word(w[0], w[1], w[2], w[3], w[4], w[5], w[6]) for w in raw]
        return self._words[page_no]

    def line_ends(self, page_no: int) -> set[int]:
        """Indices of words that are the last word on their text line."""
        words = self.words(page_no)
        return {
            i
            for i in range(len(words))
            if i + 1 == len(words) or (words[i].block, words[i].line) != (words[i + 1].block, words[i + 1].line)
        }

    def page_text(self, page_no: int) -> str:
        if page_no not in self._texts:
            with self._lock:
                self._texts[page_no] = self._doc[page_no].get_text("text", flags=_TEXT_FLAGS)
        return self._texts[page_no]

    def paper_context(self, max_chars: int = 2500) -> str:
        """Title plus the start of page 1 (usually title, authors and abstract)."""
        first = self.page_text(0) if self.page_count else ""
        return f"Title: {self.title}\n\n{first[:max_chars]}".strip()

    def full_text(self, max_chars: int = 300_000) -> tuple[str, bool]:
        """All pages, each wrapped in ``<page number="N">``; returns ``(text, truncated)``.

        The cap keeps requests within what every provider accepts (about 75k tokens); very long papers are cut at
        a page boundary and the caller says so in the prompt.
        """
        parts, size, truncated = [], 0, False
        for page in range(self.page_count):
            chunk = f'<page number="{page + 1}">\n{self.page_text(page).strip()}\n</page>'
            if parts and size + len(chunk) > max_chars:
                truncated = True
                break
            parts.append(chunk)
            size += len(chunk) + 2
        return "\n\n".join(parts), truncated

    def passage(self, page_no: int, start: int, end: int, radius: int = 60) -> str:
        """Words around word indices ``start..end`` (inclusive) on a page."""
        words = self.words(page_no)
        return " ".join(w.text for w in words[max(0, start - radius) : end + radius + 1])

    def render(self, page_no: int, scale: float = 1.0) -> RenderedPage:
        """Render a page at ``scale`` pixels per point as packed RGB."""
        with self._lock:
            pix = self._doc[page_no].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
            return RenderedPage(pix.width, pix.height, pix.stride, bytes(pix.samples))

    def render_png(self, page_no: int, zoom: float = 1.0) -> bytes:
        with self._lock:
            pix = self._doc[page_no].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return pix.tobytes("png")

    def word_at(self, page_no: int, x: float, y: float) -> int | None:
        """Index of the word containing point (x, y) in PDF points, if any."""
        for i, w in enumerate(self.words(page_no)):
            if w.contains(x, y):
                return i
        return None
