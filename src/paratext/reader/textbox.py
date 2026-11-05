"""A text box for paragraph-length input: it wraps, grows with its text up to a few lines, then scrolls."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QFrame, QPlainTextEdit, QSizePolicy


class GrowingTextEdit(QPlainTextEdit):
    """Wraps long text onto new lines and grows from ``min_lines`` to ``max_lines`` visible lines.

    Past ``max_lines`` the height stays put and a vertical scroll bar appears. Enter emits ``submitted``
    (Shift+Enter starts a new line). ``text``/``setText`` mirror ``QLineEdit``, so callers can treat it like one.
    """

    submitted = Signal()

    def __init__(self, max_lines: int = 4, min_lines: int = 1, parent=None):
        super().__init__(parent)
        self.max_lines, self.min_lines = max_lines, min_lines
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # see _fit
        self.setTabChangesFocus(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self._fit()

    # QLineEdit-style API
    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str) -> None:  # noqa: N802  (Qt naming)
        self.setPlainText(text)

    def visual_lines(self) -> int:
        """Lines as displayed, counting wrapped lines (the plain-text layout measures its height in lines)."""
        return max(1, round(self.document().documentLayout().documentSize().height()))

    def height_for_lines(self, lines: int) -> int:
        margin = self.document().documentMargin()
        return int(lines * self.fontMetrics().lineSpacing() + 2 * margin + 2 * self.frameWidth()) + 1

    def _fit(self, *_) -> None:
        lines = self.visual_lines()
        # The scroll bar only exists past max_lines: one that comes and goes while the box grows would change the
        # wrap width, and with it the line count, and leave the box a line short.
        overflow = lines > self.max_lines
        policy = Qt.ScrollBarPolicy.ScrollBarAsNeeded if overflow else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        if self.verticalScrollBarPolicy() != policy:
            self.setVerticalScrollBarPolicy(policy)
            lines = self.visual_lines()  # the wrap width changed with the scroll bar
            QTimer.singleShot(0, self._fit)  # and again once Qt has finished re-laying it out
        height = self.height_for_lines(min(max(lines, self.min_lines), self.max_lines))
        if self.height() != height or self.minimumHeight() != height:
            self.setFixedHeight(height)

    def keyPressEvent(self, event) -> None:  # noqa: N802  (Qt override)
        submit = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        if submit and not self.isReadOnly() and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            event.accept()
            self.submitted.emit()
            return
        super().keyPressEvent(event)


class ResultText(GrowingTextEdit):
    """Read-only, frameless and selectable: a label that never clips its text (it scrolls past ``max_lines``)."""

    def __init__(self, max_lines: int = 6, parent=None):
        super().__init__(max_lines=max_lines, parent=parent)
        self.setReadOnly(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.viewport().setAutoFillBackground(False)
        self.setStyleSheet("QPlainTextEdit { background: transparent; }")
        self._fit()
