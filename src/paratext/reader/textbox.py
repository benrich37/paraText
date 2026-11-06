"""Text widgets that never clip their text.

``GrowingTextEdit`` is a box for paragraph-length input: it wraps, grows with its text up to a few lines, then
scrolls. ``WrappedLabel`` is a word-wrapped label that always has room for all of its lines.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextOption
from PySide6.QtWidgets import QFrame, QLabel, QPlainTextEdit, QSizePolicy


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
        # Deferred refits go through a timer the box owns, so none can fire after the box is deleted.
        self._refit = QTimer(self)
        self._refit.setSingleShot(True)
        self._refit.setInterval(0)
        self._refit.timeout.connect(self._fit)
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
            self._refit.start()  # and again once Qt has finished re-laying it out
        height = self.height_for_lines(min(max(lines, self.min_lines), self.max_lines))
        if self.height() != height or self.minimumHeight() != height:
            self.setFixedHeight(height)

    # The text rewraps when the width changes (a splitter drag, a dialog shown after its text was set), and the
    # document does not always report the new line count, which left the box at its old height.
    def resizeEvent(self, event) -> None:  # noqa: N802  (Qt override)
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._refit.start()

    def showEvent(self, event) -> None:  # noqa: N802  (Qt override)
        super().showEvent(event)
        self._refit.start()

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


class WrappedLabel(QLabel):
    """A word-wrapped label that takes the full width it is given and the height all of its lines need there.

    In a ``QFormLayout`` a wrapped ``QLabel`` got about 20 characters of width and a row height worked out for some
    other width, so its last line was cut off even with free space below (reported issues, 2026-11-05). This label
    fixes its height to ``heightForWidth`` of its actual width whenever it is shown or its text or width changes,
    so the layout has to make room.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def needed_height(self) -> int:
        return self.heightForWidth(self.width()) if self.text() else 0

    def _fit(self) -> None:
        if not self.isVisible():  # before the first show the width is a placeholder that wants far too many lines
            return
        needed = max(self.needed_height(), 0)
        if self.minimumHeight() != needed or self.maximumHeight() != needed:
            self.setFixedHeight(needed)  # exact: a taller size hint would otherwise pull in spare height as gaps

    def setText(self, text: str) -> None:  # noqa: N802  (Qt naming)
        super().setText(text)
        self._fit()

    def resizeEvent(self, event) -> None:  # noqa: N802  (Qt override)
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:  # noqa: N802  (Qt override)
        super().showEvent(event)
        self._fit()
