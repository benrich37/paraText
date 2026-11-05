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


SAMPLE_PAGES = [
    "A Study of Catalysis\n\n"
    "Abstract. We use density functional theory (DFT) to study the oxygen reduction reaction (ORR) "
    "on single-atom catalysts. The adsorption free energy of each intermediate sets the limiting potential.",
    "Methods. All DFT calculations use the generalized gradient approximation with a plane-wave basis. "
    "The limiting potential is computed from the computational hydrogen electrode model.",
]


def highlight_pdf(path, page: int = 0):
    """Edit a PDF in place the way Preview does when you highlight: add an annotation, save incrementally.

    The text is unchanged but the file's bytes (and so its SHA-256) are not.
    """
    import pymupdf

    doc = pymupdf.open(path)
    target = doc[page]
    target.add_highlight_annot(pymupdf.Rect(30, 30, 200, 50))
    doc.saveIncr()
    doc.close()
    return path


def make_sample_pdf(path, pages=None, title="A Study of Catalysis"):
    """Write a small text PDF (one textbox per page) and return its path."""
    import pymupdf

    doc = pymupdf.open()
    for text in pages or SAMPLE_PAGES:
        page = doc.new_page(width=420, height=300)
        page.insert_textbox(pymupdf.Rect(30, 30, 390, 280), text, fontsize=11)
    doc.set_metadata({"title": title})
    doc.save(path)
    doc.close()
    return path


SAMPLE_GLOSSARY = {
    "oxygen reduction reaction": "The electrochemical reaction that turns O2 into water in fuel cells.",
    "limiting potential": "The electrode potential at which every reaction step becomes downhill in free energy.",
    "plane-wave basis": "A way of representing electron wavefunctions as sums of waves, natural for crystals.",
}


class FakeProvider:
    """A scripted provider: returns glossary JSON for terms present on the page."""

    name = "fake"

    def __init__(self, glossary=None, explanation="A short explanation.", error=None, web=False):
        self.glossary = SAMPLE_GLOSSARY if glossary is None else glossary
        self.explanation = explanation
        self.error = error
        self.web = web  # whether it claims web search, like claude-cli and anthropic
        self.calls = []

    @property
    def supports_web(self):
        return self.web

    @property
    def cache_key(self):
        return "fake"

    @property
    def summary(self):
        return "fake model"

    def complete(self, system, prompt, json_schema=None, web=False):
        import json
        import re

        if web and not self.web:
            raise AssertionError("web=True sent to a provider without web search")
        self.calls.append({"system": system, "prompt": prompt, "json_schema": json_schema, "web": web})
        if self.error is not None:
            raise self.error
        if json_schema is None:
            return self.explanation
        page = re.search(r"<page[^>]*>(.*)</page>", prompt, re.DOTALL).group(1)
        page = " ".join(page.split()).lower()
        terms = [{"term": t, "explanation": e} for t, e in self.glossary.items() if t.lower() in page]
        return "Here you go:\n```json\n" + json.dumps({"terms": terms}) + "\n```"


class FakeIssueProvider(FakeProvider):
    """Answers the "Log an issue" prompt with a fixed structured write-up (FakeProvider only knows glossary pages)."""

    writeup = {"title": "Tooltip hides page text", "category": "ui", "description": "The tooltip covers the term."}

    def complete(self, system, prompt, json_schema=None):
        import json

        self.calls.append({"system": system, "prompt": prompt, "json_schema": json_schema})
        if self.error is not None:
            raise self.error
        return "Sure:\n" + json.dumps(self.writeup)
