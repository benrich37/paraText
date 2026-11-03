"""Dialog for editing the reader profile (what the user knows and needs help with)."""

from __future__ import annotations

import copy

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
)

from paratext.profile import UserProfile


def _lines(widget: QPlainTextEdit) -> list[str]:
    return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]


class ProfileDialog(QDialog):
    def __init__(self, profile: UserProfile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About you")
        self.resize(640, 620)
        self.profile = copy.deepcopy(profile)
        root = QVBoxLayout(self)
        intro = QLabel(
            "Explanations are written for the audience in the toolbar plus what you say here. "
            "Everything is stored locally and only sent to the AI provider you choose. "
            "One concept per line in the lists."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        root.addLayout(form, 1)

        self.background_edit = QLineEdit(self.profile.background)
        self.background_edit.setPlaceholderText("e.g. computational chemist; DFT and electrocatalysis; new to kinetics")
        self.background_edit.textChanged.connect(self._refresh_preview)
        form.addRow("Background:", self.background_edit)

        self.specialties_edit = self._list_edit(self.profile.specialties, "areas you know deeply")
        form.addRow("Specialties:", self.specialties_edit)
        self.known_edit = self._list_edit(self.profile.known, "concepts that need no explanation")
        form.addRow("Know well:", self.known_edit)
        self.needs_help_edit = self._list_edit(self.profile.needs_help, "concepts to explain carefully, every time")
        form.addRow("Need help with:", self.needs_help_edit)

        self.preview = QLabel()
        self.preview.setWordWrap(True)
        self.preview.setStyleSheet("color: #5c5f66; font-style: italic;")
        form.addRow("The model is told:", self.preview)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh_preview()

    def _list_edit(self, items: list[str], placeholder: str) -> QPlainTextEdit:
        edit = QPlainTextEdit("\n".join(items))
        edit.setPlaceholderText(placeholder)
        edit.setMaximumHeight(90)
        edit.textChanged.connect(self._refresh_preview)
        return edit

    def profile_from_form(self) -> UserProfile:
        return UserProfile(
            background=self.background_edit.text(),
            specialties=_lines(self.specialties_edit),
            known=_lines(self.known_edit),
            needs_help=_lines(self.needs_help_edit),
            notes=list(self.profile.notes),
            path=self.profile.path,
        )

    def _refresh_preview(self) -> None:
        text = self.profile_from_form().to_prompt()
        self.preview.setText(text or "(nothing yet: explanations use only the audience line)")

    def accept(self) -> None:
        self.profile = self.profile_from_form()
        super().accept()
