"""A hover explanation window that stays until the reader dismisses it.

``QToolTip`` hides itself after a timeout and on small mouse moves, which made explanations vanish while they
were being read. This frameless window stays until the mouse hovers another term, the reader clicks or scrolls
the page, presses Escape, or the window loses focus. The text is selectable.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

POPUP_STYLE = (
    "QFrame { color: #1b1b1b; background-color: #fff9db; border: 1px solid #adb5bd; border-radius: 4px; }"
    "QLabel { color: #1b1b1b; background: transparent; border: none; }"
)
MAX_WIDTH = 440
GAP = 6  # pixels between the term and the popup


class ExplanationPopup(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(POPUP_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        self.label = QLabel()
        self.label.setTextFormat(Qt.TextFormat.RichText)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setMaximumWidth(MAX_WIDTH)
        layout.addWidget(self.label)

    def text(self) -> str:
        return self.label.text()

    def show_for(self, html: str, anchor: QRect) -> None:
        """Show ``html`` below ``anchor`` (global screen coordinates), above it if there is no room below."""
        self.label.setText(html)
        self.adjustSize()
        size = self.sizeHint()
        screen = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        x = min(max(anchor.left(), area.left()), area.right() - size.width() + 1)
        y = anchor.bottom() + GAP
        if y + size.height() > area.bottom() and anchor.top() - GAP - size.height() >= area.top():
            y = anchor.top() - GAP - size.height()
        y = min(max(y, area.top()), area.bottom() - size.height() + 1)
        self.move(QPoint(x, y))
        self.show()
