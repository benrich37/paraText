"""The paraText reader window (Qt).

- Underlined terms show an explanation when hovered; clicking one shows it in
  the side panel, where "More depth" asks for a fuller explanation.
- Dragging across words (or clicking one) selects a phrase; "Explain
  selection" explains it in the context of the surrounding passage.

Engine callbacks arrive on worker threads and are re-emitted as Qt signals,
which Qt delivers on the GUI thread.
"""

from __future__ import annotations

import html
import logging
import os

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextBrowser,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from paratext.ai.providers import ProviderError
from paratext.config import Config
from paratext.engine import ContextEngine
from paratext.issues import IssueContext, issues_path, log_issue
from paratext.pdf import PdfDocument
from paratext.profile import UserProfile
from paratext.reader.pageview import UNDERLINE_COLORS, DocumentView, TermSpan, line_rects
from paratext.reader.popup import ExplanationPopup
from paratext.reader.profile_dialog import ProfileDialog
from paratext.reader.setup import SetupDialog

log = logging.getLogger(__name__)

# Explicit colours so the tooltip reads the same in light and dark themes
TOOLTIP_STYLE = "QToolTip { color: #1b1b1b; background-color: #fff9db; border: 1px solid #adb5bd; padding: 6px; }"


class Subject:
    """What the side panel is about: a phrase at word indices start..end of a page."""

    def __init__(self, phrase: str, page: int, start: int, end: int, term_key: str | None = None):
        self.phrase, self.page, self.start, self.end, self.term_key = phrase, page, start, end, term_key


class EngineSignals(QObject):
    page_done = Signal(int, object, object)  # page, entries, error
    proofread_done = Signal(int, object, object)  # page, counts, error
    explained = Signal(str, object, object)  # phrase, text, error
    answered = Signal(str, object, object)  # question, answer, error
    issue_logged = Signal(object, object)  # (path, ai_problem), error


class _IssueJob(QRunnable):
    """Runs ``log_issue`` (which may call the provider) off the GUI thread."""

    def __init__(self, fn, signals: EngineSignals):
        super().__init__()
        self.fn, self.signals = fn, signals

    def run(self) -> None:
        try:
            self.signals.issue_logged.emit(self.fn(), None)
        except Exception as e:  # shown in the status bar
            self.signals.issue_logged.emit(None, e)


class ReaderWindow(QMainWindow):
    def __init__(
        self,
        config: Config | None = None,
        pdf_path=None,
        provider_name=None,
        executor=None,
        profile: UserProfile | None = None,
    ):
        super().__init__()
        self.config = config or Config()
        self.profile = profile or UserProfile()
        self.executor = executor
        self.provider_name = provider_name or self.config.default_provider or "none"
        self.audience = self.config.audience
        self.doc: PdfDocument | None = None
        self.engine: ContextEngine | None = None
        self.subject: Subject | None = None
        self._glossary_version = 0
        self._signals = EngineSignals()
        self._signals.page_done.connect(self._on_page_done)
        self._signals.proofread_done.connect(self._on_proofread_done)
        self._signals.explained.connect(self._on_explained)
        self._signals.answered.connect(self._on_answered)
        self._signals.issue_logged.connect(self._on_issue_logged)
        self.pool = QThreadPool.globalInstance()

        self.setWindowTitle("paraText reader")
        self.resize(1200, 850)
        QApplication.instance().setStyleSheet(TOOLTIP_STYLE)
        self.popup = ExplanationPopup()
        self._build_ui()
        self.view.viewport().installEventFilter(self)  # clicks, scrolling and keys dismiss the popup
        self._update_provider_ui()
        if pdf_path:
            self.open_pdf(pdf_path)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        bar = QToolBar("Main")
        bar.setMovable(False)
        self.addToolBar(bar)

        open_action = QAction("Open…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.ask_open)
        bar.addAction(open_action)
        bar.addSeparator()

        self.prev_action = QAction("◀", self)
        self.prev_action.setShortcut(QKeySequence("PgUp"))
        self.prev_action.triggered.connect(lambda: self.go_to(self.current_page() - 1))
        bar.addAction(self.prev_action)
        self.page_spin = QSpinBox()
        self.page_spin.setRange(1, 1)
        self.page_spin.valueChanged.connect(lambda v: self.go_to(v - 1))
        bar.addWidget(self.page_spin)
        self.page_count_label = QLabel(" / –  ")
        bar.addWidget(self.page_count_label)
        self.next_action = QAction("▶", self)
        self.next_action.setShortcut(QKeySequence("PgDown"))
        self.next_action.triggered.connect(lambda: self.go_to(self.current_page() + 1))
        bar.addAction(self.next_action)
        bar.addSeparator()

        zoom_out = QAction("−", self)
        zoom_out.setShortcut(QKeySequence.StandardKey.ZoomOut)
        zoom_out.triggered.connect(lambda: self.view.zoom_by(1 / 1.2))
        zoom_in = QAction("+", self)
        zoom_in.setShortcut(QKeySequence.StandardKey.ZoomIn)
        zoom_in.triggered.connect(lambda: self.view.zoom_by(1.2))
        fit = QAction("Fit width", self)
        fit.triggered.connect(lambda: self.view.fit_width())
        bar.addAction(zoom_out)
        bar.addAction(zoom_in)
        bar.addAction(fit)
        bar.addSeparator()

        self.analyze_action = QAction("Explain whole paper", self)
        self.analyze_action.setToolTip("Find and explain terms on every page now, instead of as you read")
        self.analyze_action.triggered.connect(self.analyze_all)
        bar.addAction(self.analyze_action)
        self.proofread_action = QAction("Proofread", self)
        self.proofread_action.setToolTip(
            "Have the current AI model re-read each explained page and fix or drop wrong explanations"
        )
        self.proofread_action.triggered.connect(self.proofread_all)
        bar.addAction(self.proofread_action)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding, spacer.sizePolicy().verticalPolicy())
        bar.addWidget(spacer)
        bar.addWidget(QLabel("AI: "))
        self.provider_box = QComboBox()
        self.provider_box.setMinimumWidth(140)
        self._fill_provider_box()
        self.provider_box.currentTextChanged.connect(self._provider_box_changed)
        bar.addWidget(self.provider_box)
        self.setup_button = QPushButton("Set up AI…")
        self.setup_button.clicked.connect(self.open_setup)
        bar.addWidget(self.setup_button)
        bar.addWidget(QLabel("  Explain for: "))
        self.audience_edit = QLineEdit(self.audience)
        self.audience_edit.setMinimumWidth(260)
        self.audience_edit.setPlaceholderText("who the explanations are for")
        self.audience_edit.editingFinished.connect(lambda: self.set_audience(self.audience_edit.text()))
        self.audience_edit.setCursorPosition(0)
        bar.addWidget(self.audience_edit)
        self.profile_button = QPushButton("About you…")
        self.profile_button.setToolTip("Tell the model what you know well and what needs careful explanation")
        self.profile_button.clicked.connect(self.open_profile)
        bar.addWidget(self.profile_button)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.view = DocumentView()
        self.view.termHovered.connect(self._on_hover)
        self.view.termClicked.connect(self.show_term)
        self.view.selectionChanged.connect(self._on_selection)
        self.view.currentPageChanged.connect(self._on_page_changed)
        self.view.visiblePagesChanged.connect(self._on_visible_changed)
        splitter.addWidget(self.view)

        side = QWidget()
        layout = QVBoxLayout(side)
        self.info_bar = QFrame()
        self.info_bar.setFrameShape(QFrame.Shape.StyledPanel)
        self.info_bar.setStyleSheet("QFrame { background: #fff3bf; color: #1b1b1b; border-radius: 4px; }")
        info_layout = QHBoxLayout(self.info_bar)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label, 1)
        info_button = QPushButton("Set up AI…")
        info_button.clicked.connect(self.open_setup)
        info_layout.addWidget(info_button)
        layout.addWidget(self.info_bar)

        self.panel_title = QLabel()
        self.panel_title.setWordWrap(True)
        self.panel_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.panel_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.panel_title)
        self.panel_text = QTextBrowser()
        self.panel_text.setOpenExternalLinks(True)
        layout.addWidget(self.panel_text, 1)
        self.panel_footer = QLabel()
        self.panel_footer.setWordWrap(True)
        self.panel_footer.setStyleSheet("color: #868e96; font-style: italic;")
        layout.addWidget(self.panel_footer)
        buttons = QHBoxLayout()
        self.explain_button = QPushButton("Explain selection")
        self.explain_button.clicked.connect(self.explain_selection)
        self.depth_button = QPushButton("More depth")
        self.depth_button.clicked.connect(self.explain_deeper)
        buttons.addWidget(self.explain_button)
        buttons.addWidget(self.depth_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        ask_label = QLabel("Ask about the paper as a whole:")
        ask_label.setStyleSheet("margin-top: 6px;")
        layout.addWidget(ask_label)
        ask_row = QHBoxLayout()
        self.ask_edit = QLineEdit()
        self.ask_edit.setPlaceholderText("e.g. does the paper show that X causes Y?")
        self.ask_edit.setClearButtonEnabled(True)
        self.ask_edit.returnPressed.connect(self.ask_question)
        ask_row.addWidget(self.ask_edit, 1)
        self.ask_button = QPushButton("Ask")
        self.ask_button.setToolTip("Sends the whole paper's text with your question, not just the current page")
        self.ask_button.clicked.connect(self.ask_question)
        ask_row.addWidget(self.ask_button)
        layout.addLayout(ask_row)
        issue_label = QLabel("Log an issue with paraText (saved for a later development session):")
        issue_label.setStyleSheet("margin-top: 6px; color: #868e96;")
        layout.addWidget(issue_label)
        self.issue_edit = QLineEdit()
        self.issue_edit.setPlaceholderText("what went wrong or what you want changed; Enter to save")
        self.issue_edit.setClearButtonEnabled(True)
        self.issue_edit.setToolTip(f"Appends to {issues_path()}; the current AI model adds a title and write-up")
        self.issue_edit.returnPressed.connect(self.log_issue_note)
        layout.addWidget(self.issue_edit)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([850, 350])
        self.setCentralWidget(splitter)
        self.statusBar().showMessage("Open a PDF to start (Ctrl/⌘-O).")
        self.set_panel(
            "paraText",
            "Hover over an underlined term for a quick explanation. Click a term for details, or drag across "
            "any words and press “Explain selection”. Use the box below to ask about the paper as a whole.",
        )
        self._update_buttons()

    def _fill_provider_box(self) -> None:
        self.provider_box.blockSignals(True)
        self.provider_box.clear()
        names = ["none", *self.config.provider_names()]
        if self.provider_name not in names:
            names.insert(1, self.provider_name)
        self.provider_box.addItems(names)
        self.provider_box.setCurrentText(self.provider_name)
        self.provider_box.blockSignals(False)

    # ------------------------------------------------------------------
    # document / provider state
    # ------------------------------------------------------------------

    def ask_open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a PDF", "", "PDF files (*.pdf);;All files (*)")
        if path:
            self.open_pdf(path)

    def open_pdf(self, path) -> None:
        self.close_document()
        self.doc = PdfDocument(path)
        log.info("opened %s: %r, %d pages", path, self.doc.title, self.doc.page_count)
        self.setWindowTitle(f"paraText — {self.doc.title}")
        self.view.set_document(self.doc)
        self.page_spin.setRange(1, self.doc.page_count)
        self.page_count_label.setText(f" / {self.doc.page_count}  ")
        self.statusBar().showMessage(f"Opened {self.doc.title} ({self.doc.page_count} pages).")
        self._make_engine()
        self.view.fit_width()  # the view re-fits on resize until the user zooms manually
        self._on_page_changed(0)

    def close_document(self) -> None:
        self.popup.hide()
        if self.engine:
            self.engine.shutdown()
            self.engine = None
        self.view.set_document(None)
        if self.doc:
            self.doc.close()
            self.doc = None

    def closeEvent(self, event) -> None:
        self.close_document()
        super().closeEvent(event)

    def _new_executor(self):
        if self.executor is None:
            return None
        return self.executor() if callable(self.executor) else self.executor

    def _make_engine(self) -> None:
        if self.doc is None:
            return
        if self.engine:
            self.engine.shutdown()
        provider_error = None
        try:
            provider = self.config.make_provider(self.provider_name)
        except ProviderError as e:
            provider, provider_error = None, e
        self.engine = ContextEngine(
            self.doc,
            provider,
            self.config.cache_dir,
            self.audience,
            executor=self._new_executor(),
            profile=self.profile,
        )
        self._glossary_version += 1
        for item in self.view.items:
            item.spans_version = -1
        self._update_provider_ui(provider_error)
        self._refresh_visible()

    def _update_provider_ui(self, provider_error: Exception | None = None) -> None:
        has_ai = bool(self.engine and self.engine.provider)
        if provider_error:
            self.info_label.setText(f"AI provider problem: {provider_error}")
            self.info_bar.show()
            self.statusBar().showMessage(f"AI provider problem: {provider_error}")
        elif self.provider_name == "none" or not has_ai:
            self.info_label.setText(
                "No AI provider set up: only acronyms defined in the paper are explained. "
                "Connect your chat subscription, an API key or a local model."
            )
            self.info_bar.show()
        else:
            self.info_bar.hide()
        self._update_buttons()

    def _provider_box_changed(self, name: str) -> None:
        if name and name != self.provider_name:
            self.set_provider(name, save=True)

    def set_provider(self, name: str, save: bool = False) -> None:
        self.provider_name = name
        if self.provider_box.currentText() != name:
            self.provider_box.blockSignals(True)
            self.provider_box.setCurrentText(name)
            self.provider_box.blockSignals(False)
        if save:
            self.config.default_provider = None if name == "none" else name
            self._save_config()
        if self.doc:
            self._make_engine()
        else:
            self._update_provider_ui()

    def set_audience(self, audience: str) -> None:
        audience = audience.strip()
        if audience and audience != self.audience:
            self.audience = audience
            self.config.audience = audience
            self._save_config()
            if self.doc:
                self._make_engine()

    def _save_config(self) -> None:
        try:
            self.config.save()
        except OSError as e:
            self.statusBar().showMessage(f"Could not save settings: {e}")

    def open_setup(self) -> None:
        dialog = SetupDialog(self.config, current=self.provider_name, parent=self)
        if dialog.exec():
            self.config = dialog.config
            self.audience = self.config.audience
            self.audience_edit.setText(self.audience)
            self.audience_edit.setCursorPosition(0)
            self._fill_provider_box()
            self.set_provider(dialog.selected_name)

    def open_profile(self) -> None:
        dialog = ProfileDialog(self.profile, parent=self)
        if dialog.exec():
            self.profile = dialog.profile
            try:
                self.profile.save()
            except OSError as e:
                self.statusBar().showMessage(f"Could not save your profile: {e}")
            if self.doc:
                self._make_engine()
            self.statusBar().showMessage("Profile saved; explanations will use it from now on.")

    # ------------------------------------------------------------------
    # pages and glossary
    # ------------------------------------------------------------------

    def current_page(self) -> int:
        return self.view.current_page()

    def go_to(self, page: int) -> None:
        if self.doc and 0 <= page < self.doc.page_count:
            self.view.go_to(page)

    def _on_page_changed(self, page: int) -> None:
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)
        self._refresh_visible()

    def _on_visible_changed(self) -> None:
        self._refresh_visible()

    def _refresh_visible(self) -> None:
        if not self.engine:
            return
        pages = self.view.visible_pages()
        for page in pages:
            self._ensure_spans(page)
        self._request_glossary(pages)

    def _request_glossary(self, pages: list[int]) -> None:
        if not self.engine or not self.engine.provider or not pages:
            return
        wanted = sorted(set(pages) | {min(max(pages) + 1, self.doc.page_count - 1)})
        for page in wanted:
            if not self.engine.is_page_done(page):
                if page == pages[0]:
                    self.statusBar().showMessage(f"Finding terms on page {page + 1} with {self.engine.provider.name}…")
                self.engine.ensure_page(page, callback=self._signals.page_done.emit)

    def analyze_all(self) -> None:
        if not self.engine or not self.engine.provider:
            self.statusBar().showMessage("Set up an AI provider first.")
            return
        todo = [p for p in range(self.doc.page_count) if not self.engine.is_page_done(p)]
        for page in todo:
            self.engine.ensure_page(page, callback=self._signals.page_done.emit)
        self.statusBar().showMessage(f"Explaining {len(todo)} pages in the background…")

    def proofread_all(self) -> None:
        """Re-check every explained page's AI entries with the current provider."""
        if not self.engine or not self.engine.provider:
            self.statusBar().showMessage("Set up an AI provider first.")
            return
        pages = sorted(self.engine.processed_pages)
        if not pages:
            self.statusBar().showMessage("Nothing to proofread yet: no page has been explained.")
            return
        self._proofread_left = len(pages)
        self._proofread_counts = {"checked": 0, "fixed": 0, "removed": 0}
        self.statusBar().showMessage(
            f"Proofreading {len(pages)} explained pages with {self.engine.provider.cache_key}…"
        )
        for page in pages:  # callbacks may run synchronously (ImmediateExecutor), so the message is set first
            self.engine.proofread(page, callback=self._signals.proofread_done.emit)

    _proofread_left = 0
    _proofread_counts: dict = {}

    def _on_proofread_done(self, page: int, counts, error) -> None:
        self._proofread_left = max(0, self._proofread_left - 1)
        if error:
            self.statusBar().showMessage(f"Proofreading page {page + 1} failed: {error}")
        else:
            for k, v in counts.items():
                self._proofread_counts[k] = self._proofread_counts.get(k, 0) + v
            if counts["fixed"] or counts["removed"]:
                self._glossary_version += 1
                self._refresh_visible()
                if self.subject and self.subject.term_key:
                    entry = self.engine.entry(self.subject.term_key)
                    if entry is not None:
                        self.set_panel(entry.term, entry.explanation, self._footer(entry.source, entry))
        if self._proofread_left == 0:
            c = self._proofread_counts
            self.statusBar().showMessage(
                f"Proofread {c.get('checked', 0)} explanations: {c.get('fixed', 0)} corrected, "
                f"{c.get('removed', 0)} removed."
            )

    def _ensure_spans(self, page: int) -> None:
        item = self.view.page_item(page)
        if item.spans_version == self._glossary_version:
            return
        words = self.doc.words(page)
        terms = []
        for span in self.engine.spans(page):
            entry = self.engine.entry(span.key)
            color = UNDERLINE_COLORS.get(entry.source if entry else "ai", UNDERLINE_COLORS["ai"])
            terms.append(TermSpan(span, line_rects(words, span.start, span.end), color))
        item.spans = terms
        item.spans_version = self._glossary_version
        item.update()

    def _on_page_done(self, page: int, entries, error) -> None:
        if error:
            self.statusBar().showMessage(f"Page {page + 1}: {error}")
            return
        self._glossary_version += 1
        self._refresh_visible()
        done = len(self.engine.processed_pages) if self.engine else 0
        self.statusBar().showMessage(
            f"Page {page + 1}: {len(entries)} new terms explained by {self.engine.provider.name} "
            f"({done}/{self.doc.page_count} pages done)."
        )

    # ------------------------------------------------------------------
    # hover tooltips
    # ------------------------------------------------------------------

    def _on_hover(self, page: int, term: TermSpan | None, screen_pos: QPoint) -> None:
        # Leaving a term keeps the popup open (it closes on click, scroll, Escape or another term).
        if term is None or not self.engine:
            return
        entry = self.engine.entry(term.span.key)
        if entry is None:
            return
        text = (
            f"<b>{html.escape(entry.term)}</b><br>{html.escape(entry.explanation)}"
            f"<br><span style='color:#5c5f66'><i>{html.escape(self._footer(entry.source, entry))}"
            " · click for more</i></span>"
        )
        rect = self.view.term_viewport_rect(page, term)
        top_left = self.view.viewport().mapToGlobal(rect.topLeft())
        self.popup.show_for(text, QRect(top_left, rect.size()))

    def eventFilter(self, obj, event) -> bool:  # noqa: N802  (Qt override)
        if obj is self.view.viewport() and event.type() in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.Wheel,
            QEvent.Type.KeyPress,
        ):
            self.popup.hide()
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self.popup.isVisible():
            self.popup.hide()
            return
        super().keyPressEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.popup.hide()
        super().changeEvent(event)

    def _footer(self, source: str, entry=None) -> str:
        """Who produced an explanation: the provider's cache key names the tool, model and effort."""
        if source == "acronym":
            return "Defined in the paper"
        provider = (entry.provider if entry else "") or (
            self.engine.provider.cache_key if self.engine and self.engine.provider else "AI"
        )
        text = f"AI-generated by {provider}; may contain mistakes"
        if entry is not None and entry.proofread:
            text += f" · proofread by {entry.proofread}"
        return text

    # ------------------------------------------------------------------
    # side panel
    # ------------------------------------------------------------------

    def set_panel(self, title: str, body: str, footer: str = "") -> None:
        self.panel_title.setText(title)
        self.panel_text.setPlainText(body)
        self.panel_footer.setText(footer)
        self.panel_footer.setVisible(bool(footer))

    def panel_body(self) -> str:
        return self.panel_text.toPlainText()

    def _update_buttons(self) -> None:
        has_ai = bool(self.engine and self.engine.provider)
        self.explain_button.setEnabled(has_ai and self.view.selection() is not None)
        self.depth_button.setEnabled(has_ai and self.subject is not None)
        self.analyze_action.setEnabled(has_ai)
        self.proofread_action.setEnabled(has_ai)
        self.ask_edit.setEnabled(has_ai)
        self.ask_button.setEnabled(has_ai)

    def show_term(self, page: int, term: TermSpan) -> None:
        self.popup.hide()
        self.view.clear_selection()
        entry = self.engine.entry(term.span.key) if self.engine else None
        phrase = " ".join(w.text for w in self.doc.words(page)[term.span.start : term.span.end + 1])
        self.subject = Subject(entry.term if entry else phrase, page, term.span.start, term.span.end, term.span.key)
        body = entry.explanation if entry else ""
        detailed = self.engine.cached_explanation(self.subject.phrase, page, True) if self.engine else None
        if detailed:
            body += "\n\n" + detailed
        self.set_panel(self.subject.phrase, body, self._footer(entry.source if entry else "ai", entry))
        self._update_buttons()

    def selected_text(self) -> str:
        sel = self.view.selection()
        if sel is None or not self.doc:
            return ""
        page, start, end = sel
        return " ".join(w.text for w in self.doc.words(page)[start : end + 1])

    def _on_selection(self, page: int, start: int, end: int) -> None:
        self.subject = Subject(self.selected_text(), page, start, end)
        cached = self.engine.cached_explanation(self.subject.phrase, page, False) if self.engine else None
        self.set_panel(self.subject.phrase, cached or "Press “Explain selection” to explain this in context.")
        self._update_buttons()

    def explain_selection(self) -> None:
        sel = self.view.selection()
        if sel is None or not self.engine:
            return
        page, start, end = sel
        self.subject = Subject(self.selected_text(), page, start, end)
        self._request_explanation(self.subject, detailed=False)

    def explain_deeper(self) -> None:
        if self.subject and self.engine:
            self._request_explanation(self.subject, detailed=True)

    def _request_explanation(self, subject: Subject, detailed: bool) -> None:
        if not self.engine.provider:
            self.set_panel(subject.phrase, "No AI provider selected. Choose one in the toolbar.")
            return
        self._pending_subject = (subject, detailed)
        self.set_panel(subject.phrase, "Thinking…" if not detailed else self.panel_body() + "\n\nThinking…")
        self.engine.explain(
            subject.phrase, subject.page, subject.start, subject.end, detailed, callback=self._signals.explained.emit
        )

    _pending_subject: tuple[Subject, bool] | None = None

    def _on_explained(self, phrase: str, text, error) -> None:
        if self._pending_subject is None:
            return
        subject, detailed = self._pending_subject
        if self.subject is not subject:
            return
        if error:
            self.set_panel(phrase, f"Could not get an explanation: {error}")
            return
        if detailed and subject.term_key:
            entry = self.engine.entry(subject.term_key)
            text = (entry.explanation + "\n\n" + text) if entry else text
        self.set_panel(phrase, text, self._footer("ai"))

    # ------------------------------------------------------------------
    # questions about the whole paper
    # ------------------------------------------------------------------

    _pending_question: str | None = None

    def ask_question(self) -> None:
        question = self.ask_edit.text().strip()
        if not question or not self.engine:
            return
        if not self.engine.provider:
            self.set_panel(question, "No AI provider selected. Choose one in the toolbar.")
            return
        self.subject = None
        self.view.clear_selection()
        self._pending_question = question
        self.set_panel(question, "Reading the whole paper…")
        self._update_buttons()
        self.engine.ask(question, callback=self._signals.answered.emit)

    def _on_answered(self, question: str, answer, error) -> None:
        if self._pending_question != question:
            return
        self._pending_question = None
        if error:
            self.set_panel(question, f"Could not get an answer: {error}")
            return
        self.ask_edit.clear()
        self.set_panel(question, answer + self._earlier_questions(question), self._footer("ai"))

    def _earlier_questions(self, current: str, limit: int = 5) -> str:
        """Previous Q&A for this paper (newest first), appended below the current answer."""
        key = self.engine.question_key(current)
        earlier = [q for q in reversed(self.engine.questions) if self.engine.question_key(q["question"]) != key]
        if not earlier:
            return ""
        blocks = [f"Q: {q['question']}\nA: {q['answer']}" for q in earlier[:limit]]
        return "\n\n— Earlier questions —\n\n" + "\n\n".join(blocks)

    # ------------------------------------------------------------------
    # issue log for testing sessions
    # ------------------------------------------------------------------

    def issue_context(self) -> IssueContext:
        provider = self.engine.provider if self.engine else None
        return IssueContext(
            document=self.doc.title if self.doc else "",
            path=str(self.doc.path) if self.doc else "",
            page=self.current_page() + 1 if self.doc else None,
            page_count=self.doc.page_count if self.doc else None,
            provider=provider.cache_key if provider else "none",
            audience=self.audience,
            panel_title=self.panel_title.text(),
        )

    def log_issue_note(self) -> None:
        note = self.issue_edit.text().strip()
        if not note:
            return
        context = self.issue_context()
        provider = self.engine.provider if self.engine else None
        self.issue_edit.setEnabled(False)
        self.statusBar().showMessage("Logging the issue…")
        self.pool.start(_IssueJob(lambda: log_issue(note, context, provider), self._signals))

    def _on_issue_logged(self, result, error) -> None:
        self.issue_edit.setEnabled(True)
        if error:
            self.statusBar().showMessage(f"Could not log the issue: {error}")
            return
        path, problem = result
        self.issue_edit.clear()
        self.issue_edit.setFocus()
        suffix = f" (without AI write-up: {problem})" if problem else ""
        self.statusBar().showMessage(f"Issue logged to {path}{suffix}", 8000)
        log.info("issue logged to %s%s", path, suffix)


class FileOpenHandler(QObject):
    """Open documents that the OS hands to a running app (macOS "Open With", double-click, drag to the Dock).

    macOS delivers such files as Apple Events, not as command-line arguments; Qt turns them into
    ``QFileOpenEvent``s on the ``QApplication``. Install with ``app.installEventFilter(handler)``.
    """

    def __init__(self, window: ReaderWindow):
        super().__init__(window)
        self.window = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802  (Qt override)
        if event.type() == QEvent.Type.FileOpen and event.file():
            log.info("file-open event: %s", event.file())
            self.window.open_pdf(event.file())
            self.window.show()
            self.window.raise_()
            self.window.activateWindow()
            return True
        return super().eventFilter(obj, event)


def run(pdf_path=None, provider_name=None, config_path=None) -> int:
    import sys

    if os.environ.get("PARATEXT_LOG"):  # the macOS app bundle sets this; see macapp.py
        logging.basicConfig(level=os.environ["PARATEXT_LOG"].upper(), format="%(asctime)s %(name)s: %(message)s")
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("paraText")
    app.setApplicationDisplayName("paraText")
    window = ReaderWindow(Config.load(config_path), pdf_path, provider_name, profile=UserProfile.load())
    app.installEventFilter(FileOpenHandler(window))
    window.show()
    return app.exec()
