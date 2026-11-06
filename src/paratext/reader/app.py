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
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QPoint,
    QRect,
    QRunnable,
    QSettings,
    Qt,
    QThreadPool,
    QUrl,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
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
from paratext.glossary import Span
from paratext.issues import IssueContext, issues_path, log_issue
from paratext.links import Link, LinkStore
from paratext.pdf import PdfDocument
from paratext.profile import UserProfile
from paratext.reader.pageview import UNDERLINE_COLORS, DocumentView, TermSpan, line_rects
from paratext.reader.popup import ExplanationPopup
from paratext.reader.profile_dialog import ProfileDialog
from paratext.reader.setup import SetupDialog
from paratext.reader.textbox import GrowingTextEdit, WrappedLabel

log = logging.getLogger(__name__)

# Explicit colours so the tooltip reads the same in light and dark themes
TOOLTIP_STYLE = "QToolTip { color: #1b1b1b; background-color: #fff9db; border: 1px solid #adb5bd; padding: 6px; }"


def ui_state_path() -> Path:
    """Where the window remembers its pane sizes: ``$PARATEXT_UI_STATE`` or ``~/.config/paratext/ui.ini``."""
    return Path(os.environ.get("PARATEXT_UI_STATE", Path.home() / ".config" / "paratext" / "ui.ini"))


def _pane() -> tuple[QWidget, QVBoxLayout]:
    """A section of the side panel's vertical splitter."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 4, 0, 4)
    return widget, layout


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
    link_described = Signal(object, object, object)  # link, text, error


class _CallJob(QRunnable):
    """Runs ``fn`` off the GUI thread and emits ``signal(result, error)``."""

    def __init__(self, fn, signal):
        super().__init__()
        self.fn, self.signal = fn, signal

    def run(self) -> None:
        try:
            self.signal.emit(self.fn(), None)
        except Exception as e:  # shown in the status bar
            self.signal.emit(None, e)


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
        self._signals.link_described.connect(self._on_link_described)
        self.pool = QThreadPool.globalInstance()

        self.setWindowTitle("paraText reader")
        self.resize(1200, 850)
        QApplication.instance().setStyleSheet(TOOLTIP_STYLE)
        self.popup = ExplanationPopup()
        self.links = LinkStore()
        self._child_windows: list[ReaderWindow] = []
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
        self.info_label = WrappedLabel()  # WrappedLabels keep every line; a wrapped QLabel could lose its last
        info_layout.addWidget(self.info_label, 1)
        info_button = QPushButton("Set up AI…")
        info_button.clicked.connect(self.open_setup)
        info_layout.addWidget(info_button)
        layout.addWidget(self.info_bar)

        # The explanation, the history and the linked files share the height; drag the handles between them
        # like the one between the page view and this panel. The two text boxes below size themselves.
        self.side_splitter = QSplitter(Qt.Orientation.Vertical)
        self.side_splitter.setChildrenCollapsible(False)
        layout.addWidget(self.side_splitter, 1)

        explain_pane, pane = _pane()
        self.panel_title = WrappedLabel()
        self.panel_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.panel_title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pane.addWidget(self.panel_title)
        self.panel_text = QTextBrowser()
        self.panel_text.setOpenExternalLinks(True)
        self.panel_text.setMinimumHeight(60)
        pane.addWidget(self.panel_text, 1)
        self.panel_footer = WrappedLabel()
        self.panel_footer.setStyleSheet("color: #868e96; font-style: italic;")
        pane.addWidget(self.panel_footer)
        buttons = QHBoxLayout()
        self.explain_button = QPushButton("Explain selection")
        self.explain_button.clicked.connect(self.explain_selection)
        self.depth_button = QPushButton("More depth")
        self.depth_button.clicked.connect(self.explain_deeper)
        buttons.addWidget(self.explain_button)
        buttons.addWidget(self.depth_button)
        buttons.addStretch(1)
        pane.addLayout(buttons)
        self.side_splitter.addWidget(explain_pane)

        history_pane, pane = _pane()
        self.history_label = QLabel("Questions asked about this paper:")
        pane.addWidget(self.history_label)
        self.history_list = QListWidget()
        self.history_list.setMinimumHeight(36)
        self.history_list.setToolTip("Click to bring an earlier answer or explanation back")
        self.history_list.itemClicked.connect(self._history_clicked)
        pane.addWidget(self.history_list, 1)
        self.side_splitter.addWidget(history_pane)

        links_pane, pane = _pane()
        pane.addWidget(QLabel("Linked files (supporting information, data):"))
        self.links_list = QListWidget()
        self.links_list.setMinimumHeight(36)
        self.links_list.setToolTip("Double-click to open: PDFs in a new paraText window, other files with the system")
        self.links_list.itemDoubleClicked.connect(self.open_link)
        self.links_list.itemSelectionChanged.connect(self._update_buttons)
        pane.addWidget(self.links_list, 1)
        link_row = QHBoxLayout()
        self.link_pdf_button = QPushButton("Link PDF…")
        self.link_pdf_button.setToolTip("Link supporting-information or related PDFs to this paper")
        self.link_pdf_button.clicked.connect(self.link_pdf)
        self.link_data_button = QPushButton("Link data…")
        self.link_data_button.setToolTip("Link data files of any type to this paper")
        self.link_data_button.clicked.connect(self.link_data)
        self.link_folder_button = QPushButton("Link folder…")
        self.link_folder_button.clicked.connect(self.link_folder)
        self.open_link_button = QPushButton("Open")
        self.open_link_button.clicked.connect(lambda: self.open_link(self.links_list.currentItem()))
        self.describe_link_button = QPushButton("Describe…")
        self.describe_link_button.setToolTip(
            "Say what the file contains and when the AI should look at it (questions include linked files)"
        )
        self.describe_link_button.clicked.connect(self.describe_selected_link)
        self.unlink_button = QPushButton("Unlink")
        self.unlink_button.clicked.connect(self.unlink_selected)
        for b in (self.link_pdf_button, self.link_data_button, self.link_folder_button):
            link_row.addWidget(b)
        link_row.addStretch(1)
        link_row.addWidget(self.open_link_button)
        link_row.addWidget(self.describe_link_button)
        link_row.addWidget(self.unlink_button)
        pane.addLayout(link_row)
        self.side_splitter.addWidget(links_pane)
        self.side_splitter.setStretchFactor(0, 1)
        self.side_splitter.setSizes([420, 110, 150])

        ask_label = QLabel("Ask about the paper as a whole:")
        ask_label.setStyleSheet("margin-top: 6px;")
        layout.addWidget(ask_label)
        ask_row = QHBoxLayout()
        self.ask_edit = GrowingTextEdit(max_lines=4)
        self.ask_edit.setPlaceholderText(
            "e.g. does the paper show that X causes Y? (Enter asks; Shift+Enter starts a new line)"
        )
        self.ask_edit.submitted.connect(self.ask_question)
        ask_row.addWidget(self.ask_edit, 1)
        self.ask_button = QPushButton("Ask")
        self.ask_button.setToolTip("Sends the whole paper's text with your question, not just the current page")
        self.ask_button.clicked.connect(self.ask_question)
        ask_row.addWidget(self.ask_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(ask_row)
        self.web_check = QCheckBox("Let the AI look up cited papers and search the web")
        self.web_check.setChecked(self.config.allow_web)
        self.web_check.toggled.connect(self.set_allow_web)
        layout.addWidget(self.web_check)
        issue_label = QLabel("Log an issue with paraText (saved for a later development session):")
        issue_label.setStyleSheet("margin-top: 6px; color: #868e96;")
        layout.addWidget(issue_label)
        self.issue_edit = GrowingTextEdit(max_lines=4)
        self.issue_edit.setPlaceholderText(
            "what went wrong or what you want changed (Enter saves; Shift+Enter starts a new line)"
        )
        self.issue_edit.setToolTip(f"Appends to {issues_path()}; the current AI model adds a title and write-up")
        self.issue_edit.submitted.connect(self.log_issue_note)
        layout.addWidget(self.issue_edit)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([850, 350])
        self.splitter = splitter
        self.setCentralWidget(splitter)
        self._restore_layout()
        self.ai_label = QLabel()
        self.ai_label.setStyleSheet("color: #495057; margin-right: 6px;")
        self.statusBar().addPermanentWidget(self.ai_label)
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
        self._refresh_links()
        self._show_history()

    def close_document(self) -> None:
        self.popup.hide()
        self.links_list.clear()
        self.history_list.clear()
        if self.engine:
            self.engine.shutdown()
            self.engine = None
        self.view.set_document(None)
        if self.doc:
            self.doc.close()
            self.doc = None

    def closeEvent(self, event) -> None:
        self._save_layout()
        self.close_document()
        super().closeEvent(event)

    def _layout_settings(self) -> QSettings:
        return QSettings(str(ui_state_path()), QSettings.Format.IniFormat)

    def _restore_layout(self) -> None:
        """Bring back the pane sizes the reader dragged to last time (main split and the side panel's sections)."""
        settings = self._layout_settings()
        for key, splitter in (("main_splitter", self.splitter), ("side_splitter", self.side_splitter)):
            state = settings.value(key)
            if isinstance(state, QByteArray) and not state.isEmpty():
                splitter.restoreState(state)

    def _save_layout(self) -> None:
        settings = self._layout_settings()
        settings.setValue("main_splitter", self.splitter.saveState())
        settings.setValue("side_splitter", self.side_splitter.saveState())
        settings.sync()

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
            link_store=self.links,
            allow_web=self.config.allow_web,
        )
        self._glossary_version += 1
        for item in self.view.items:
            item.spans_version = -1
        self._update_provider_ui(provider_error)
        self._refresh_visible()

    def _update_provider_ui(self, provider_error: Exception | None = None) -> None:
        has_ai = bool(self.engine and self.engine.provider)
        self._show_ai_settings(provider_error)
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

    def _show_ai_settings(self, provider_error: Exception | None = None) -> None:
        """The status bar always names the active tool, model and effort, not just the provider."""
        provider = self.engine.provider if self.engine else None
        if provider is None and self.provider_name != "none" and self.doc is None:
            try:  # no document yet: show what the configured provider would be
                provider = self.config.make_provider(self.provider_name)
            except ProviderError as e:
                provider_error = provider_error or e
        if provider_error:
            text, tip = f"AI: {self.provider_name} (problem)", str(provider_error)
        elif provider is None:
            text, tip = "AI: none", "No AI provider selected"
        else:
            text, tip = f"AI: {provider.name} — {provider.summary}", f"Cache key: {provider.cache_key}"
            if self.config.allow_web and getattr(provider, "supports_web", False):
                text += " · web search on"
            log.info("provider %s: %s", provider.name, provider.summary)
        self.ai_label.setText(text)
        self.ai_label.setToolTip(tip)
        self.provider_box.setToolTip(tip)

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
        """Write this window's default provider and audience on top of what is on disk.

        Provider settings (model, effort, keys) are only edited by the setup dialog; re-reading the file first
        means a second window or instance holding an older copy cannot overwrite them.
        """
        try:
            fresh = Config.load(self.config.path)
            fresh.default_provider = self.config.default_provider
            fresh.audience = self.config.audience
            fresh.cache_dir = self.config.cache_dir
            fresh.allow_web = self.config.allow_web
            fresh.save(self.config.path)
            self.config.providers = fresh.providers
            self.config.path = fresh.path
        except OSError as e:
            self.statusBar().showMessage(f"Could not save settings: {e}")

    def adopt_config(self, config: Config) -> None:
        """Take over settings saved by the setup dialog, updating the Config object shared with other windows."""
        self.config.default_provider = config.default_provider
        self.config.audience = config.audience
        self.config.providers = config.providers
        self.config.cache_dir = config.cache_dir
        self.config.allow_web = config.allow_web
        self.config.path = config.path or self.config.path
        self.audience = self.config.audience
        self.audience_edit.setText(self.audience)
        self.audience_edit.setCursorPosition(0)
        self._fill_provider_box()

    def set_allow_web(self, on: bool) -> None:
        """The reader's permission for web search (cited papers, literature) in questions and "More depth"."""
        on = bool(on)
        if self.web_check.isChecked() != on:
            self.web_check.setChecked(on)  # re-enters through toggled
            return
        if self.config.allow_web == on:
            return
        self.config.allow_web = on
        if self.engine:
            self.engine.allow_web = on
        self._save_config()
        self._show_ai_settings()
        self._update_buttons()

    def open_setup(self) -> None:
        # start from the file, not this window's copy, so settings saved elsewhere are shown and kept
        current = Config.load(self.config.path) if self.config.path and self.config.path.exists() else self.config
        dialog = SetupDialog(current, current=self.provider_name, parent=self)
        if dialog.exec():
            self.adopt_config(dialog.config)
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
        for e in self.engine.explained_spans(page):  # selections already explained: double underline, click to recall
            span = Span(self.engine.explanation_key(e["phrase"], page, False), e["start"], e["end"])
            terms.append(TermSpan(span, line_rects(words, e["start"], e["end"]), UNDERLINE_COLORS["user"], "explained"))
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
        if term.kind == "explained":
            e = self._explained_record(page, term)
            explanation = self.engine.explanations.get(term.span.key, "") if e else ""
            if not e or not explanation:
                return
            title, body, footer = e["phrase"], explanation, self._footer("ai") + " (your selection)"
        else:
            entry = self.engine.entry(term.span.key)
            if entry is None:
                return
            title, body, footer = entry.term, entry.explanation, self._footer(entry.source, entry)
        text = (
            f"<b>{html.escape(title)}</b><br>{html.escape(body)}"
            f"<br><span style='color:#5c5f66'><i>{html.escape(footer)} · click for more</i></span>"
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

    def _footer(self, source: str, entry=None, web: bool = False) -> str:
        """Who produced an explanation: the provider's cache key names the tool, model and effort."""
        if source == "acronym":
            return "Defined in the paper"
        provider = (entry.provider if entry else "") or (
            self.engine.provider.cache_key if self.engine and self.engine.provider else "AI"
        )
        text = f"AI-generated by {provider}; may contain mistakes"
        if web:
            text += " · web search was allowed: check the sources it names"
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
        has_doc = self.doc is not None
        for b in (self.link_pdf_button, self.link_data_button, self.link_folder_button):
            b.setEnabled(has_doc)
        selected = has_doc and self.links_list.currentItem() is not None
        self.open_link_button.setEnabled(selected)
        self.describe_link_button.setEnabled(selected)
        self.unlink_button.setEnabled(selected)
        self.ask_edit.setEnabled(has_ai)
        self.ask_button.setEnabled(has_ai)
        provider = self.engine.provider if self.engine else None
        if provider is None:
            self.web_check.setEnabled(False)
            self.web_check.setToolTip("Set up an AI provider first.")
        elif not getattr(provider, "supports_web", False):
            self.web_check.setEnabled(False)
            self.web_check.setToolTip(
                f"{provider.name} cannot search the web from paraText. Claude Code (claude-cli) and the Anthropic "
                "API can; for other command-line tools add 'web_args' to their settings in the config file."
            )
        else:
            self.web_check.setEnabled(True)
            self.web_check.setToolTip(
                "Applies to whole-paper questions and “More depth”: the AI may look up the papers this one cites "
                "and search the literature when the paper and linked files do not settle it, and names its sources. "
                "Slower, and uses more of your plan or API budget. Off: only the paper and linked files are used."
            )

    def show_term(self, page: int, terms) -> None:
        """Show the clicked span(s); with several (a term inside an explained selection) list them to switch."""
        terms = list(terms) if isinstance(terms, (list, tuple)) else [terms]
        self.popup.hide()
        self.view.clear_selection()
        if len(terms) > 1:
            self._show_span_choices(page, terms)
        else:
            self._show_history()
        self._show_span(page, terms[0])

    def _explained_record(self, page: int, term: TermSpan) -> dict | None:
        return next(
            (
                e
                for e in self.engine.explained_spans(page)
                if (e["start"], e["end"]) == (term.span.start, term.span.end)
            ),
            None,
        )

    def _show_span(self, page: int, term: TermSpan) -> None:
        if term.kind == "explained":
            e = self._explained_record(page, term)
            phrase = (
                e["phrase"]
                if e
                else " ".join(w.text for w in self.doc.words(page)[term.span.start : term.span.end + 1])
            )
            self.subject = Subject(phrase, page, term.span.start, term.span.end)
            body = self.engine.cached_explanation(phrase, page, False) or ""
            detailed = self.engine.cached_explanation(phrase, page, True)
            if detailed:
                body += "\n\n" + detailed
            self.set_panel(phrase, body, self._footer("ai") + " (your selection)")
            self._update_buttons()
            return
        entry = self.engine.entry(term.span.key) if self.engine else None
        phrase = " ".join(w.text for w in self.doc.words(page)[term.span.start : term.span.end + 1])
        self.subject = Subject(entry.term if entry else phrase, page, term.span.start, term.span.end, term.span.key)
        body = entry.explanation if entry else ""
        detailed = self.engine.cached_explanation(self.subject.phrase, page, True) if self.engine else None
        if detailed:
            body += "\n\n" + detailed
        self.set_panel(self.subject.phrase, body, self._footer(entry.source if entry else "ai", entry))
        self._update_buttons()

    # ------------------------------------------------------------------
    # history: questions asked, and explanations stacked under one click
    # ------------------------------------------------------------------

    def _show_history(self) -> None:
        """List the questions asked about this paper (newest first) in the history box."""
        self.history_label.setText("Questions asked about this paper:")
        self.history_list.clear()
        if not self.engine:
            return
        for q in reversed(self.engine.questions):
            item = QListWidgetItem(f"Q: {q['question']}" + ("  🌐" if q.get("web") else ""))
            item.setToolTip(q["answer"])
            item.setData(Qt.ItemDataRole.UserRole, ("question", q))
            self.history_list.addItem(item)

    def _show_span_choices(self, page: int, terms) -> None:
        """Several explanations under one click: list them so the reader can switch between them."""
        self.history_label.setText("Explanations at this spot (click to switch):")
        self.history_list.clear()
        words = self.doc.words(page)
        for term in terms:
            if term.kind == "explained":
                e = self._explained_record(page, term)
                label = "Your selection: " + (e["phrase"] if e else "")
            else:
                entry = self.engine.entry(term.span.key)
                label = (
                    ("Term: " + entry.term)
                    if entry
                    else " ".join(w.text for w in words[term.span.start : term.span.end + 1])
                )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ("span", (page, term)))
            self.history_list.addItem(item)
        self.history_list.setCurrentRow(0)

    def _history_clicked(self, item) -> None:
        kind, payload = item.data(Qt.ItemDataRole.UserRole)
        if kind == "question":
            self.subject = None
            self.view.clear_selection()
            self.set_panel(payload["question"], payload["answer"], self._footer("ai", web=bool(payload.get("web"))))
            self._update_buttons()
        elif kind == "span":
            page, term = payload
            self._show_span(page, term)

    def selected_text(self) -> str:
        sel = self.view.selection()
        if sel is None or not self.doc:
            return ""
        page, start, end = sel
        return " ".join(w.text for w in self.doc.words(page)[start : end + 1])

    def _on_selection(self, page: int, start: int, end: int) -> None:
        self._show_history()
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
        web = detailed and self.engine.web_enabled
        thinking = "Thinking (and searching the literature)…" if web else "Thinking…"
        self.set_panel(subject.phrase, thinking if not detailed else self.panel_body() + "\n\n" + thinking)
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
        web = detailed and self.engine.cached_explanation(phrase, subject.page, True, web=True) is not None
        self.set_panel(phrase, text, self._footer("ai", web=web))
        if not subject.term_key:  # a selection: it now carries a double underline that brings this back
            self._glossary_version += 1
            self._refresh_visible()

    # ------------------------------------------------------------------
    # linked files: SI PDFs, data files, folders
    # ------------------------------------------------------------------

    def _refresh_links(self) -> None:
        self.links_list.clear()
        if self.doc is None:
            self._update_buttons()
            return
        icons = {"pdf": "📄", "data": "📊", "folder": "📁"}
        for link in self.links.links(self.doc.sha256):
            summary = f" — {link.description}" if link.description else ""
            item = QListWidgetItem(f"{icons.get(link.kind, '•')} {link.name}{summary}")
            item.setData(Qt.ItemDataRole.UserRole, link)
            tip = link.path if link.exists else f"{link.path}\n(not found)"
            if link.description:
                by = "your description" if link.description_by == "user" else f"described by {link.description_by}"
                tip += f"\n\n{link.description}\n({by})"
            item.setToolTip(tip)
            if not link.exists:
                item.setForeground(QColor("#868e96"))
            self.links_list.addItem(item)
        self._update_buttons()

    def _start_dir(self) -> str:
        return str(self.doc.path.parent) if self.doc else ""

    def _add_links(self, paths, kind: str | None = None) -> None:
        if self.doc is None:
            return
        added = [
            self.links.add(self.doc.sha256, p, kind, doc_path=str(self.doc.path), doc_title=self.doc.title)
            for p in paths
            if p
        ]
        self._refresh_links()
        if added:
            self.links_list.setCurrentRow(self.links_list.count() - 1)
            self.statusBar().showMessage(f"Linked {len(added)} item(s) to {self.doc.title}.", 6000)
        # let the AI say what each new file contains, so it knows when to consult it
        if self.engine and self.engine.provider:
            for link in added:
                if not link.description:
                    self.engine.describe_link(link, callback=self._signals.link_described.emit)

    def _on_link_described(self, link, text, error) -> None:
        if error:
            self.statusBar().showMessage(f"Could not describe {link.name}: {error}")
            return
        self._refresh_links()
        self.statusBar().showMessage(f"{link.name}: {text}", 10000)

    def describe_selected_link(self) -> None:
        link = self.selected_link()
        if link is None or self.doc is None:
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Describe a linked file",
            f"What does {link.name} contain, and when should the AI look at it?",
            link.description,
        )
        if ok:
            self.links.set_description(self.doc.sha256, link.path, text, by="user")
            self._refresh_links()

    def link_pdf(self) -> None:
        start = self._start_dir()
        paths, _ = QFileDialog.getOpenFileNames(self, "Link PDFs to this paper", start, "PDF files (*.pdf)")
        self._add_links(paths, "pdf")

    def link_data(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Link data files to this paper", self._start_dir(), "All files (*)"
        )
        self._add_links(paths)

    def link_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Link a folder to this paper", self._start_dir())
        self._add_links([path], "folder")

    def selected_link(self) -> Link | None:
        item = self.links_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def unlink_selected(self) -> None:
        link = self.selected_link()
        if link and self.doc:
            self.links.remove(self.doc.sha256, link.path)
            self._refresh_links()

    def open_link(self, item) -> None:
        link = item.data(Qt.ItemDataRole.UserRole) if item else None
        if link is None:
            return
        if not link.exists:
            self.statusBar().showMessage(f"Not found: {link.path}")
            return
        if link.kind == "pdf":
            self.open_in_new_window(link.path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(link.path))

    def _forget_child(self, window) -> None:
        if window in self._child_windows:
            self._child_windows.remove(window)

    def open_in_new_window(self, path) -> ReaderWindow:
        """A second reader window (same config, provider and profile), e.g. for a linked SI PDF."""
        window = ReaderWindow(self.config, path, self.provider_name, executor=self.executor, profile=self.profile)
        self._child_windows.append(window)
        window.destroyed.connect(lambda *_: self._forget_child(window))
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.show()
        return window

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
        web = self.engine.web_enabled
        reading = "Reading the whole paper and searching the literature…" if web else "Reading the whole paper…"
        self.set_panel(question, reading)
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
        record = next((q for q in reversed(self.engine.questions) if q["answer"] == answer), {})
        self.set_panel(question, answer, self._footer("ai", web=bool(record.get("web"))))
        self._show_history()

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
        self.pool.start(_CallJob(lambda: log_issue(note, context, provider), self._signals.issue_logged))

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
