"""Dialog for connecting an AI provider without editing the config file.

Lists every way to connect (subscription CLIs, API keys, local models) with a
readiness check, shows only the fields the chosen one needs, can fetch the
model list from OpenAI-compatible servers, sends a test prompt, and saves to
the config file.
"""

from __future__ import annotations

import copy
import shlex

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from paratext.ai.providers import (
    GROUP_TITLES,
    PRESET_INFO,
    PRESETS,
    ProviderError,
    list_models,
    make_provider,
    preset_status,
    probe_claude_models,
    provider_capabilities,
)
from paratext.config import Config
from paratext.reader.textbox import ResultText

CUSTOM_NAMES = {"custom-openai": "Custom OpenAI-compatible server", "custom-command": "Custom command"}
CUSTOM_SETTINGS = {
    "custom-openai": {"kind": "openai", "base_url": "http://localhost:8000/v1", "model": ""},
    "custom-command": {"kind": "command", "command": []},
}
TEST_SYSTEM = "You are a connectivity check for the paraText reader."
TEST_PROMPT = "Reply with the single word OK."


def _use_full_width(label: QLabel) -> None:
    """Let a wrapped label take the whole form width (its size hint is about 20 characters wide otherwise)."""
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class _JobSignals(QObject):
    finished = Signal(object, object)  # result, error


class _Job(QRunnable):
    def __init__(self, fn, signals: _JobSignals):
        super().__init__()
        self.fn, self.signals = fn, signals

    def run(self) -> None:
        try:
            self.signals.finished.emit(self.fn(), None)
        except Exception as e:  # reported in the dialog
            self.signals.finished.emit(None, e)


class SetupDialog(QDialog):
    def __init__(self, config: Config, current: str | None = None, parent=None, pool: QThreadPool | None = None):
        super().__init__(parent)
        self.setWindowTitle("Set up AI for paraText")
        self.resize(900, 560)
        self.config = copy.deepcopy(config)
        self.pool = pool or QThreadPool.globalInstance()
        self.selected_name: str | None = None
        self._settings: dict = {}
        self._test_signals = _JobSignals()
        self._test_signals.finished.connect(self._test_finished)
        self._models_signals = _JobSignals()
        self._models_signals.finished.connect(self._models_fetched)
        self._build_ui()
        self._populate_list()
        self._select_initial(current)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        intro = QLabel(
            "Choose how paraText should reach an AI model. Consumer chat plans do not come with API keys, "
            "so the first group uses each vendor's own command-line tool, signed in with your subscription."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)
        body = QHBoxLayout()
        root.addLayout(body, 1)

        self.list = QListWidget()
        self.list.setMinimumWidth(300)
        self.list.currentItemChanged.connect(self._item_changed)
        body.addWidget(self.list)

        right = QWidget()
        form = QFormLayout(right)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        body.addWidget(right, 1)
        self.form = form

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold;")
        form.addRow(self.title_label)
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setOpenExternalLinks(True)
        self.description_label.setTextFormat(Qt.TextFormat.RichText)
        form.addRow(self.description_label)
        self.status_label = QLabel()  # single line: wrapping labels get stale heights when rows toggle
        form.addRow("Status:", self.status_label)

        key_row = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.textChanged.connect(self._update_status)
        key_row.addWidget(self.key_edit, 1)
        self.show_key = QCheckBox("Show")
        self.show_key.toggled.connect(
            lambda on: self.key_edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )
        key_row.addWidget(self.show_key)
        self.key_row = QWidget()
        self.key_row.setLayout(key_row)
        form.addRow("API key:", self.key_row)
        self.key_note = QLabel()
        self.key_note.setWordWrap(True)
        self.key_note.setStyleSheet("color: #868e96;")
        form.addRow("", self.key_note)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("http://host:port/v1")
        form.addRow("Server URL:", self.base_url_edit)

        model_row = QHBoxLayout()
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.currentTextChanged.connect(self._update_status)
        model_row.addWidget(self.model_combo, 1)
        self.fetch_button = QPushButton("Fetch models")
        self.fetch_button.clicked.connect(self.fetch_models)
        model_row.addWidget(self.fetch_button)
        self.model_row = QWidget()
        self.model_row.setLayout(model_row)
        form.addRow("Model:", self.model_row)
        self.model_note = QLabel()
        self.model_note.setWordWrap(True)
        self.model_note.setStyleSheet("color: #868e96;")
        form.addRow("", self.model_note)

        self.effort_combo = QComboBox()
        form.addRow("Effort:", self.effort_combo)
        self.effort_note = QLabel()
        self.effort_note.setWordWrap(True)
        self.effort_note.setStyleSheet("color: #868e96;")
        form.addRow("", self.effort_note)

        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText("program and arguments; the prompt is sent on stdin")
        self.command_edit.textChanged.connect(self._update_status)
        form.addRow("Command:", self.command_edit)

        self.audience_edit = QLineEdit(self.config.audience)
        form.addRow("Explain for:", self.audience_edit)

        test_row = QHBoxLayout()
        self.test_button = QPushButton("Send a test prompt")
        self.test_button.clicked.connect(self.run_test)
        test_row.addWidget(self.test_button)
        test_row.addStretch(1)
        form.addRow("", test_row)
        # A read-only text box, not a QLabel: a wrapped label here got a stale one-line height and clipped the
        # test reply to "Success! The model" (reported issue, 2026-11-05). This one grows, then scrolls.
        self.result_label = ResultText(max_lines=6)
        form.addRow("", self.result_label)
        for label in (self.description_label, self.key_note, self.model_note, self.effort_note):
            _use_full_width(label)

        self.buttons = QDialogButtonBox()
        self.save_button = self.buttons.addButton("Save and use", QDialogButtonBox.ButtonRole.AcceptRole)
        self.buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

    def _populate_list(self) -> None:
        self.list.clear()
        for group in ("subscription", "api-key", "local"):
            self._add_header(GROUP_TITLES[group])
            for name, info in PRESET_INFO.items():
                if info.group == group:
                    self._add_option(name, info.title)
        self._add_header("Custom")
        for name, settings in self.config.providers.items():
            if name not in PRESETS and settings.get("preset") not in PRESETS:
                self._add_option(name, f"{name} ({settings.get('kind', '?')})")
        for name, title in CUSTOM_NAMES.items():
            if name not in self.config.providers:
                self._add_option(name, title)

    def _add_header(self, text: str) -> None:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        self.list.addItem(item)

    def _add_option(self, name: str, title: str) -> None:
        ready, _ = preset_status(name, self.config.providers.get(name) or CUSTOM_SETTINGS.get(name))
        item = QListWidgetItem(f"{'✓' if ready else '○'}  {title}")
        item.setData(Qt.ItemDataRole.UserRole, name)
        self.list.addItem(item)

    def _select_initial(self, current: str | None) -> None:
        names = self.option_names()
        if current in names:
            self.select(current)
            return
        for name in names:  # first ready option, else the first option
            if preset_status(name, self.config.providers.get(name))[0]:
                self.select(name)
                return
        if names:
            self.select(names[0])

    def option_names(self) -> list[str]:
        return [
            self.list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list.count())
            if self.list.item(i).data(Qt.ItemDataRole.UserRole)
        ]

    def select(self, name: str) -> None:
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentRow(i)
                return

    # ------------------------------------------------------------------
    # form state
    # ------------------------------------------------------------------

    def _item_changed(self, item, _previous=None) -> None:
        name = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not name:
            return
        self.selected_name = name
        saved = self.config.providers.get(name)
        if saved is not None:
            self._settings = dict(saved)
        elif name in PRESETS:
            self._settings = {"preset": name}
        else:
            self._settings = dict(CUSTOM_SETTINGS.get(name, {}))
        merged = self._merged()
        kind = merged.get("kind")
        info = PRESET_INFO.get(name)
        self.title_label.setText(info.title if info else CUSTOM_NAMES.get(name) or f"{name} ({kind})")
        self.description_label.setText(_linkify(info.description) if info else _custom_description(kind))
        self.result_label.clear()

        self.key_edit.blockSignals(True)
        self.key_edit.setText(merged.get("api_key") or "")
        self.key_edit.blockSignals(False)
        env = merged.get("api_key_env") or ("ANTHROPIC_API_KEY" if kind == "anthropic" else None)
        if env:
            import os

            if os.environ.get(env):
                self.key_note.setText(f"Leave blank to keep using ${env} from your environment.")
            else:
                self.key_note.setText(f"Stored privately in your config file. (Or set ${env} and leave this blank.)")
        self.base_url_edit.setText(merged.get("base_url", ""))
        caps = provider_capabilities(merged)
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        suggested = list(info.suggested_models) if info else []
        if kind == "command" and suggested:
            suggested.insert(0, "")  # blank = the tool's default model
        self.model_combo.addItems(suggested)
        self.model_combo.setCurrentText(merged.get("model", ""))
        self.model_combo.blockSignals(False)
        self.model_note.setText(caps["model_help"])
        self.fetch_button.setText("Check models" if kind == "command" else "Fetch models")
        self.effort_combo.blockSignals(True)
        self.effort_combo.clear()
        if caps["effort"]:
            self.effort_combo.addItems(list(caps["effort"]))
            default = "low" if kind == "anthropic" else ""
            self.effort_combo.setCurrentText(merged.get("effort", default))
        self.effort_combo.blockSignals(False)
        self.effort_note.setText(caps["effort_help"])
        command = merged.get("command") or []
        self.command_edit.blockSignals(True)
        self.command_edit.setText(shlex.join(command) if isinstance(command, list) else command)
        self.command_edit.blockSignals(False)

        self.form.setRowVisible(self.key_row, caps["api_key"])
        self.form.setRowVisible(self.key_note, caps["api_key"])
        self.form.setRowVisible(self.base_url_edit, caps["base_url"])
        self.form.setRowVisible(self.command_edit, caps["command"])
        self.form.setRowVisible(self.model_row, caps["model"])
        self.form.setRowVisible(self.model_note, caps["model"] and bool(caps["model_help"]))
        self.fetch_button.setVisible(caps["fetch_models"])
        self.form.setRowVisible(self.effort_combo, caps["effort"] is not None)
        self.form.setRowVisible(self.effort_note, caps["effort"] is not None)
        self._update_status()
        self.form.invalidate()
        self.form.activate()

    def _merged(self) -> dict:
        merged = dict(PRESETS.get(self._settings.get("preset", ""), {}))
        merged.update(self._settings)
        return merged

    def current_settings(self) -> dict:
        """The provider settings as edited in the form (what gets saved)."""
        settings = dict(self._settings)
        merged = self._merged()
        kind = merged.get("kind")
        preset = PRESETS.get(settings.get("preset", ""), {})
        key = self.key_edit.text().strip()
        if key:
            settings["api_key"] = key
        else:
            settings.pop("api_key", None)
        caps = provider_capabilities(merged)
        if caps["model"]:
            model = self.model_combo.currentText().strip()
            if model or kind != "command":
                settings["model"] = model
            else:
                settings.pop("model", None)
        if kind == "openai":
            url = self.base_url_edit.text().strip()
            if url and url != preset.get("base_url"):
                settings["base_url"] = url
            elif url:
                settings.pop("base_url", None)
        if caps["effort"] is not None:
            effort = self.effort_combo.currentText()
            if effort:
                settings["effort"] = effort
            else:
                settings.pop("effort", None)
        if kind == "command":
            settings["command"] = shlex.split(self.command_edit.text())
        return settings

    def _update_status(self, *_) -> None:
        if not self.selected_name:
            return
        ready, message = preset_status(self.selected_name, self.current_settings())
        self.status_label.setText(("✓ " if ready else "○ ") + message)
        self.status_label.setStyleSheet("color: #2b8a3e;" if ready else "color: #c92a2a;")
        self.test_button.setEnabled(True)

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------

    def _provider(self):
        return make_provider(self.selected_name, self.current_settings())

    def fetch_models(self) -> None:
        merged = {**self._merged(), **self.current_settings()}
        if merged.get("kind") == "command":
            command = merged.get("command") or []
            self.result_label.setText("Asking the tool which models it can use (one short prompt per alias)…")
            self.fetch_button.setEnabled(False)
            self.pool.start(_Job(lambda: probe_claude_models(command), self._models_signals))
            return
        base_url = self.base_url_edit.text().strip() or merged.get("base_url", "")
        key = self.key_edit.text().strip() or None
        env = merged.get("api_key_env")
        if not key and env:
            import os

            key = os.environ.get(env)
        self.result_label.setText("Fetching models…")
        self.fetch_button.setEnabled(False)
        self.pool.start(_Job(lambda: list_models(base_url, key), self._models_signals))

    def _models_fetched(self, models, error) -> None:
        self.fetch_button.setEnabled(True)
        if error:
            self.result_label.setText(f"Could not list models: {error}")
            return
        if isinstance(models, dict):  # alias -> resolved id, from a subscription CLI probe
            mapping = ", ".join(f"{alias} = {model}" for alias, model in models.items())
            models = ["", *models, *models.values()]
            current = self.model_combo.currentText()
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(models)
            self.model_combo.setCurrentText(current if current in models else "")
            self.model_combo.blockSignals(False)
            self._update_status()
            self.result_label.setText(f"Usable now: {mapping}.")
            return
        current = self.model_combo.currentText()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        self.model_combo.addItems(models)
        self.model_combo.setCurrentText(current if current in models or not models else models[0])
        self.model_combo.blockSignals(False)
        self._update_status()
        self.result_label.setText(f"{len(models)} models available." if models else "The server listed no models.")

    def run_test(self) -> None:
        try:
            provider = self._provider()
        except ProviderError as e:
            self.result_label.setText(f"Not ready: {e}")
            return
        self.result_label.setText("Sending a test prompt…")
        self.test_button.setEnabled(False)
        self.pool.start(_Job(lambda: provider.complete(TEST_SYSTEM, TEST_PROMPT), self._test_signals))

    def _test_finished(self, reply, error) -> None:
        self.test_button.setEnabled(True)
        if error:
            self.result_label.setText(f"Test failed: {error}")
        else:
            self.result_label.setText(f"Success! The model replied: {str(reply).strip()[:2000]}")

    def accept(self) -> None:
        if not self.selected_name:
            return
        settings = self.current_settings()
        try:
            make_provider(self.selected_name, settings)
        except ProviderError as e:
            self.result_label.setText(f"Cannot save yet: {e}")
            return
        self.config.providers[self.selected_name] = settings
        self.config.default_provider = self.selected_name
        audience = self.audience_edit.text().strip()
        if audience:
            self.config.audience = audience
        try:
            self.config.save()
        except OSError as e:
            self.result_label.setText(f"Could not write the config file: {e}")
            return
        super().accept()


def _linkify(text: str) -> str:
    import html
    import re

    escaped = html.escape(text)
    return re.sub(r"(https?://[^\s,)]+)", r'<a href="\1">\1</a>', escaped)


def _custom_description(kind: str | None) -> str:
    if kind == "command":
        return (
            "Any program that reads a prompt on standard input and prints the reply, e.g. a wrapper script "
            "around a vendor CLI."
        )
    return "Any server that speaks the OpenAI chat-completions protocol (vLLM, llama.cpp, Groq, Together, …)."
