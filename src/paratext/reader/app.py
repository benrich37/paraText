"""tkinter PDF reader with hover explanations for terms and phrases.

- Highlighted (underlined) terms show an explanation when hovered.
- Clicking a term shows it in the side panel, where "More depth" asks for a
  fuller explanation.
- Dragging across words selects a phrase; "Explain selection" explains it in
  the context of the surrounding passage.

AI work runs on the engine's worker threads; results come back through a
queue that the Tk main loop polls (Tk is not thread-safe).
"""

from __future__ import annotations

import base64
import queue
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, ttk

from paratext.ai.providers import ProviderError
from paratext.config import Config
from paratext.engine import ContextEngine
from paratext.glossary import Span
from paratext.pdf import PdfDocument

UNDERLINE_COLORS = {"ai": "#d9480f", "acronym": "#1971c2", "user": "#2f9e44"}
SELECTION_COLOR = "#1c7ed6"
HOVER_COLOR = "#f08c00"
TOOLTIP_BG = "#fff9db"


@dataclass
class Subject:
    """What the side panel is about: a phrase at word indices start..end of a page."""

    phrase: str
    page: int
    start: int
    end: int
    term_key: str | None = None


def line_rects(words, start: int, end: int) -> list[tuple[float, float, float, float]]:
    """Bounding boxes (one per text line) covering words ``start..end``."""
    rects: dict[tuple[int, int], list[float]] = {}
    for w in words[start : end + 1]:
        r = rects.setdefault((w.block, w.line), [w.x0, w.y0, w.x1, w.y1])
        r[0], r[1], r[2], r[3] = min(r[0], w.x0), min(r[1], w.y0), max(r[2], w.x1), max(r[3], w.y1)
    return [tuple(r) for r in rects.values()]


class ReaderApp:
    hover_delay_ms = 300
    poll_ms = 50

    def __init__(self, root: tk.Tk, config: Config | None = None, pdf_path=None, provider_name=None, executor=None):
        self.root = root
        self.config = config or Config()
        self.executor = executor
        self.provider_name = provider_name or self.config.default_provider or "none"
        self.audience = self.config.audience
        self.doc: PdfDocument | None = None
        self.engine: ContextEngine | None = None
        self.page = 0
        self.zoom = 1.0
        self._photo = None
        self._spans: list[tuple[Span, list[tuple]]] = []
        self._hover_span: Span | None = None
        self._hover_job = None
        self._tooltip: tk.Toplevel | None = None
        self._sel_anchor: int | None = None
        self._sel_end: int | None = None
        self._press_word: int | None = None
        self.subject: Subject | None = None
        self._queue: queue.Queue = queue.Queue()

        root.title("paraText reader")
        root.geometry("1100x800")
        self._build_ui()
        self._bind_keys()
        self.root.after(self.poll_ms, self._poll_queue)
        if pdf_path:
            self.open_pdf(pdf_path)
        else:
            self._draw_placeholder()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="Open…", command=self.ask_open).pack(side=tk.LEFT)
        ttk.Button(bar, text="◀", width=3, command=lambda: self.go_to(self.page - 1)).pack(side=tk.LEFT, padx=(8, 0))
        self.page_label = ttk.Label(bar, text="– / –", width=9, anchor=tk.CENTER)
        self.page_label.pack(side=tk.LEFT)
        ttk.Button(bar, text="▶", width=3, command=lambda: self.go_to(self.page + 1)).pack(side=tk.LEFT)
        ttk.Button(bar, text="−", width=3, command=lambda: self.set_zoom(self.zoom / 1.2)).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(bar, text="+", width=3, command=lambda: self.set_zoom(self.zoom * 1.2)).pack(side=tk.LEFT)

        ttk.Label(bar, text="AI:").pack(side=tk.LEFT, padx=(16, 2))
        self.provider_var = tk.StringVar(value=self.provider_name)
        self.provider_box = ttk.Combobox(
            bar, textvariable=self.provider_var, values=["none", *self.config.provider_names()], width=14
        )
        self.provider_box.pack(side=tk.LEFT)
        self.provider_box.bind("<<ComboboxSelected>>", lambda e: self.set_provider(self.provider_var.get()))

        ttk.Label(bar, text="Explain for:").pack(side=tk.LEFT, padx=(16, 2))
        self.audience_var = tk.StringVar(value=self.audience)
        audience_entry = ttk.Entry(bar, textvariable=self.audience_var, width=48)
        audience_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        audience_entry.bind("<Return>", lambda e: self.set_audience(self.audience_var.get()))

        self.status = ttk.Label(self.root, text="", anchor=tk.W, padding=(6, 2))
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        panes.pack(fill=tk.BOTH, expand=True)

        view = ttk.Frame(panes)
        self.canvas = tk.Canvas(view, background="#868e96", highlightthickness=0)
        vbar = ttk.Scrollbar(view, orient=tk.VERTICAL, command=self.canvas.yview)
        hbar = ttk.Scrollbar(view, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        vbar.pack(side=tk.RIGHT, fill=tk.Y)
        hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        panes.add(view, weight=3)

        side = ttk.Frame(panes, padding=8)
        self.panel_title = ttk.Label(side, text="", font=("TkDefaultFont", 14, "bold"), wraplength=320)
        self.panel_title.pack(side=tk.TOP, anchor=tk.W)
        self.panel_text = tk.Text(side, wrap=tk.WORD, width=40, relief=tk.FLAT, padx=4, pady=4)
        self.panel_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=6)
        self.panel_text.tag_configure("footer", foreground="#868e96", font=("TkDefaultFont", 10, "italic"))
        buttons = ttk.Frame(side)
        buttons.pack(side=tk.TOP, fill=tk.X)
        self.explain_button = ttk.Button(buttons, text="Explain selection", command=self.explain_selection)
        self.explain_button.pack(side=tk.LEFT)
        self.depth_button = ttk.Button(buttons, text="More depth", command=self.explain_deeper)
        self.depth_button.pack(side=tk.LEFT, padx=6)
        panes.add(side, weight=1)
        self.set_panel(
            "paraText",
            "Hover over an underlined term for a quick explanation. Click a term for details, or drag across "
            "any words and press “Explain selection”.",
        )
        self._update_buttons()

        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._clear_hover())
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-3, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(3, "units"))

    def _on_wheel(self, event) -> None:
        # macOS reports small deltas per notch; Windows reports multiples of 120
        delta = event.delta if abs(event.delta) < 120 else event.delta // 120
        self.canvas.yview_scroll(-delta, "units")

    def _bind_keys(self) -> None:
        r = self.root
        for seq in ("<Right>", "<Next>"):
            r.bind(seq, lambda e: self._unless_typing(e, lambda: self.go_to(self.page + 1)))
        for seq in ("<Left>", "<Prior>"):
            r.bind(seq, lambda e: self._unless_typing(e, lambda: self.go_to(self.page - 1)))
        for mod in ("Control", "Command"):
            try:
                r.bind(f"<{mod}-o>", lambda e: self.ask_open())
                r.bind(f"<{mod}-plus>", lambda e: self.set_zoom(self.zoom * 1.2))
                r.bind(f"<{mod}-equal>", lambda e: self.set_zoom(self.zoom * 1.2))
                r.bind(f"<{mod}-minus>", lambda e: self.set_zoom(self.zoom / 1.2))
            except tk.TclError:  # "Command" only exists on macOS
                pass

    @staticmethod
    def _unless_typing(event, action) -> None:
        if not isinstance(event.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
            action()

    # ------------------------------------------------------------------
    # document / provider / page state
    # ------------------------------------------------------------------

    def ask_open(self) -> None:
        path = filedialog.askopenfilename(title="Open a PDF", filetypes=[("PDF files", "*.pdf"), ("All files", "*")])
        if path:
            self.open_pdf(path)

    def open_pdf(self, path) -> None:
        if self.engine:
            self.engine.shutdown()
        if self.doc:
            self.doc.close()
        self.doc = PdfDocument(path)
        self.root.title(f"paraText — {self.doc.title}")
        self.page = 0
        self.root.update_idletasks()
        width = max(self.canvas.winfo_width(), 600)
        self.zoom = max(0.5, min(3.0, (width - 30) / self.doc.page_size(0)[0]))
        self._make_engine()
        self.show_page()

    def _make_engine(self) -> None:
        if self.doc is None:
            return
        if self.engine:
            self.engine.shutdown()
        try:
            provider = self.config.make_provider(self.provider_name)
            provider_error = None
        except ProviderError as e:
            provider, provider_error = None, e
        self.engine = ContextEngine(
            self.doc, provider, self.config.cache_dir, self.audience, executor=self._new_executor()
        )
        if provider_error:
            self.set_status(f"AI provider problem: {provider_error}  (showing acronyms only)")
        elif provider is None:
            self.set_status(
                "No AI provider selected: showing acronyms defined in the paper. "
                "Pick a provider above, or run `paratext config --init`."
            )

    def _new_executor(self):
        if self.executor is None:
            return None
        return self.executor() if callable(self.executor) else self.executor

    def set_provider(self, name: str) -> None:
        self.provider_name = name
        self._make_engine()
        self.show_page()

    def set_audience(self, audience: str) -> None:
        audience = audience.strip()
        if audience and audience != self.audience:
            self.audience = audience
            self._make_engine()
            self.show_page()

    def go_to(self, page: int) -> None:
        if self.doc and 0 <= page < self.doc.page_count and page != self.page:
            self.page = page
            self.show_page()
            self.canvas.yview_moveto(0)

    def set_zoom(self, zoom: float) -> None:
        if self.doc:
            self.zoom = max(0.3, min(5.0, zoom))
            self.show_page()

    # ------------------------------------------------------------------
    # drawing
    # ------------------------------------------------------------------

    def _draw_placeholder(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            40, 40, anchor=tk.NW, fill="white", font=("TkDefaultFont", 16), text="Open a PDF to start (Ctrl/⌘-O)."
        )

    def show_page(self) -> None:
        if not self.doc:
            return
        self._clear_hover()
        self._clear_selection()
        self.canvas.delete("all")
        png = self.doc.render_png(self.page, self.zoom)
        self._photo = tk.PhotoImage(data=base64.b64encode(png).decode())
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._photo, tags=("page",))
        self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
        self.page_label.config(text=f"{self.page + 1} / {self.doc.page_count}")
        self.draw_terms()
        self._request_glossary()

    def _request_glossary(self) -> None:
        if not self.engine or not self.engine.provider:
            return
        for page in (self.page, self.page + 1):
            if page < self.doc.page_count and not self.engine.is_page_done(page):
                started = self.engine.ensure_page(page, callback=self._threadsafe(self._on_page_done))
                if started and page == self.page:
                    self.set_status(f"Finding terms on page {page + 1} with {self.engine.provider.name}…")

    def draw_terms(self) -> None:
        self.canvas.delete("term")
        self._spans = []
        if not self.engine:
            return
        words = self.doc.words(self.page)
        z = self.zoom
        for span in self.engine.spans(self.page):
            rects = line_rects(words, span.start, span.end)
            self._spans.append((span, rects))
            entry = self.engine.entry(span.key)
            color = UNDERLINE_COLORS.get(entry.source if entry else "ai", UNDERLINE_COLORS["ai"])
            for x0, _, x1, y1 in rects:
                self.canvas.create_line(x0 * z, y1 * z + 1, x1 * z, y1 * z + 1, fill=color, width=2, tags=("term",))

    # ------------------------------------------------------------------
    # thread marshalling
    # ------------------------------------------------------------------

    def _threadsafe(self, fn):
        """Wrap a callback so it runs on the Tk thread."""
        return lambda *args: self._queue.put(lambda: fn(*args))

    def _poll_queue(self) -> None:
        try:
            while True:
                self._queue.get_nowait()()
        except queue.Empty:
            pass
        try:
            self.root.after(self.poll_ms, self._poll_queue)
        except tk.TclError:  # window closed
            pass

    def process_pending(self) -> None:
        """Run queued callbacks now (used by tests and scripts)."""
        while not self._queue.empty():
            self._queue.get_nowait()()

    def _on_page_done(self, page, entries, error) -> None:
        if error:
            self.set_status(f"Page {page + 1}: {error}")
            return
        if page == self.page:
            self.draw_terms()
            self.set_status(f"Page {page + 1}: {len(entries)} new terms explained by {self.engine.provider.name}.")

    # ------------------------------------------------------------------
    # hover tooltips
    # ------------------------------------------------------------------

    def _pdf_point(self, event) -> tuple[float, float]:
        return self.canvas.canvasx(event.x) / self.zoom, self.canvas.canvasy(event.y) / self.zoom

    def span_at(self, x: float, y: float) -> Span | None:
        """The term span under PDF point (x, y), if any."""
        for span, rects in self._spans:
            for x0, y0, x1, y1 in rects:
                if x0 <= x <= x1 and y0 <= y <= y1:
                    return span
        return None

    def _on_motion(self, event) -> None:
        if not self.doc:
            return
        span = self.span_at(*self._pdf_point(event))
        if span == self._hover_span:
            return
        self._clear_hover()
        if span is None:
            return
        self._hover_span = span
        self.canvas.config(cursor="hand2")
        z = self.zoom
        rects = next(r for s, r in self._spans if s is span)
        for x0, y0, x1, y1 in rects:
            self.canvas.create_rectangle(
                x0 * z - 1, y0 * z - 1, x1 * z + 1, y1 * z + 1, outline=HOVER_COLOR, width=1, tags=("hover",)
            )
        x_root, y_root = event.x_root, event.y_root
        self._hover_job = self.root.after(self.hover_delay_ms, lambda: self.show_tooltip(span, x_root, y_root))

    def show_tooltip(self, span: Span, x_root: int, y_root: int) -> None:
        self._hide_tooltip()
        entry = self.engine.entry(span.key) if self.engine else None
        if entry is None:
            return
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        tip.configure(background="#adb5bd")
        frame = tk.Frame(tip, background=TOOLTIP_BG, padx=8, pady=6)
        frame.pack(padx=1, pady=1)
        tk.Label(frame, text=entry.term, background=TOOLTIP_BG, font=("TkDefaultFont", 12, "bold"), anchor=tk.W).pack(
            fill=tk.X
        )
        tk.Label(
            frame, text=entry.explanation, background=TOOLTIP_BG, wraplength=380, justify=tk.LEFT, anchor=tk.W
        ).pack(fill=tk.X)
        tk.Label(
            frame,
            text=self._footer(entry.source) + "  ·  click for more",
            background=TOOLTIP_BG,
            foreground="#868e96",
            font=("TkDefaultFont", 9, "italic"),
            anchor=tk.W,
        ).pack(fill=tk.X, pady=(4, 0))
        tip.wm_geometry(f"+{x_root + 14}+{y_root + 18}")
        self._tooltip = tip

    def _hide_tooltip(self) -> None:
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None

    def _clear_hover(self) -> None:
        if self._hover_job is not None:
            self.root.after_cancel(self._hover_job)
            self._hover_job = None
        self._hover_span = None
        self.canvas.delete("hover")
        self.canvas.config(cursor="")
        self._hide_tooltip()

    def _footer(self, source: str) -> str:
        if source == "acronym":
            return "Defined in the paper"
        name = self.engine.provider.name if self.engine and self.engine.provider else "AI"
        return f"AI-generated by {name}; may contain mistakes"

    # ------------------------------------------------------------------
    # clicking and selecting
    # ------------------------------------------------------------------

    def _word_at_event(self, event) -> int | None:
        return self.doc.word_at(self.page, *self._pdf_point(event)) if self.doc else None

    def _on_press(self, event) -> None:
        self._hide_tooltip()
        self._press_word = self._word_at_event(event)
        self._clear_selection()
        self._sel_anchor = self._press_word

    def _on_drag(self, event) -> None:
        if self._sel_anchor is None:
            return
        word = self._word_at_event(event)
        if word is not None and word != self._sel_end:
            self._sel_end = word
            self._draw_selection()

    def _on_release(self, event) -> None:
        if not self.doc or self._press_word is None:
            return
        if self._sel_end is None or self._sel_end == self._press_word:
            span = self.span_at(*self._pdf_point(event))
            if span is not None:
                self._clear_selection()
                self.show_term(span)
                return
            self._sel_end = self._press_word
            self._draw_selection()
        start, end = self.selection_range()
        self.subject = Subject(self.selected_text(), self.page, start, end)
        cached = self.engine.cached_explanation(self.subject.phrase, self.page, False) if self.engine else None
        self.set_panel(self.subject.phrase, cached or "Press “Explain selection” to explain this in context.")
        self._update_buttons()

    def select_words(self, start: int, end: int) -> None:
        """Select page words ``start..end`` (inclusive), as a drag would."""
        self._sel_anchor, self._sel_end = start, end
        self._draw_selection()
        lo, hi = self.selection_range()
        self.subject = Subject(self.selected_text(), self.page, lo, hi)
        self._update_buttons()

    def selection_range(self) -> tuple[int, int] | None:
        if self._sel_anchor is None or self._sel_end is None:
            return None
        return min(self._sel_anchor, self._sel_end), max(self._sel_anchor, self._sel_end)

    def selected_text(self) -> str:
        rng = self.selection_range()
        if rng is None:
            return ""
        return " ".join(w.text for w in self.doc.words(self.page)[rng[0] : rng[1] + 1])

    def _draw_selection(self) -> None:
        self.canvas.delete("sel")
        rng = self.selection_range()
        if rng is None:
            return
        z = self.zoom
        for x0, y0, x1, y1 in line_rects(self.doc.words(self.page), *rng):
            self.canvas.create_rectangle(
                x0 * z - 1, y0 * z - 1, x1 * z + 1, y1 * z + 1, outline=SELECTION_COLOR, width=2, tags=("sel",)
            )

    def _clear_selection(self) -> None:
        self._sel_anchor = self._sel_end = None
        self.canvas.delete("sel")

    def show_term(self, span: Span) -> None:
        entry = self.engine.entry(span.key)
        phrase = " ".join(w.text for w in self.doc.words(self.page)[span.start : span.end + 1])
        self.subject = Subject(entry.term if entry else phrase, self.page, span.start, span.end, span.key)
        detailed = self.engine.cached_explanation(self.subject.phrase, self.page, True)
        body = entry.explanation if entry else ""
        if detailed:
            body += "\n\n" + detailed
        self.set_panel(self.subject.phrase, body, self._footer(entry.source if entry else "ai"))
        self._update_buttons()

    # ------------------------------------------------------------------
    # side panel and explanation requests
    # ------------------------------------------------------------------

    def set_panel(self, title: str, body: str, footer: str = "") -> None:
        self.panel_title.config(text=title)
        self.panel_text.config(state=tk.NORMAL)
        self.panel_text.delete("1.0", tk.END)
        self.panel_text.insert("1.0", body)
        if footer:
            self.panel_text.insert(tk.END, "\n\n" + footer, ("footer",))
        self.panel_text.config(state=tk.DISABLED)

    def panel_body(self) -> str:
        return self.panel_text.get("1.0", "end-1c")

    def set_status(self, text: str) -> None:
        self.status.config(text=text)

    def _update_buttons(self) -> None:
        has_ai = bool(self.engine and self.engine.provider)
        self.explain_button.state(["!disabled"] if has_ai and self.selection_range() else ["disabled"])
        self.depth_button.state(["!disabled"] if has_ai and self.subject else ["disabled"])

    def explain_selection(self) -> None:
        if self.selection_range() is None or not self.engine:
            return
        start, end = self.selection_range()
        self.subject = Subject(self.selected_text(), self.page, start, end)
        self._request_explanation(self.subject, detailed=False)

    def explain_deeper(self) -> None:
        if self.subject and self.engine:
            self._request_explanation(self.subject, detailed=True)

    def _request_explanation(self, subject: Subject, detailed: bool) -> None:
        if not self.engine.provider:
            self.set_panel(subject.phrase, "No AI provider selected. Choose one in the toolbar.")
            return
        self.set_panel(subject.phrase, "Thinking…" if not detailed else self.panel_body() + "\n\nThinking…")

        def done(phrase, text, error):
            if self.subject is not subject:
                return
            if error:
                self.set_panel(phrase, f"Could not get an explanation: {error}")
                return
            if detailed and subject.term_key:
                entry = self.engine.entry(subject.term_key)
                text = (entry.explanation + "\n\n" + text) if entry else text
            self.set_panel(phrase, text, self._footer("ai"))

        self.engine.explain(
            subject.phrase, subject.page, subject.start, subject.end, detailed, callback=self._threadsafe(done)
        )


def run(pdf_path=None, provider_name=None, config_path=None) -> None:
    root = tk.Tk()
    app = ReaderApp(root, Config.load(config_path), pdf_path, provider_name)
    try:
        root.mainloop()
    finally:
        if app.engine:
            app.engine.shutdown()
