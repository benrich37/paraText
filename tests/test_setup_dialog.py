"""Tests for the AI setup dialog (Qt offscreen)."""

import os

import pytest
from PySide6.QtCore import QThreadPool

from paratext.ai.providers import PRESETS
from paratext.config import Config
from paratext.reader.setup import SetupDialog
from paratext.testing import FakeProvider


@pytest.fixture
def dialog_factory(qtbot, tmp_path):
    def make(config=None, current=None):
        config = config or Config(cache_dir=tmp_path / "cache", path=tmp_path / "config.toml")
        dialog = SetupDialog(config, current=current)
        qtbot.addWidget(dialog)
        dialog.show()
        return dialog

    return make


def test_lists_every_preset_and_custom_options(dialog_factory):
    dialog = dialog_factory()
    names = dialog.option_names()
    assert set(PRESETS) <= set(names)
    assert "custom-openai" in names and "custom-command" in names


def test_command_preset_status(dialog_factory, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    dialog = dialog_factory(current="claude-cli")
    assert dialog.selected_name == "claude-cli"
    assert "not installed" in dialog.status_label.text()
    assert not dialog.command_edit.isHidden()
    assert dialog.key_row.isHidden() and dialog.model_row.isHidden()
    assert dialog.command_edit.text() == "claude -p"
    monkeypatch.setattr("shutil.which", lambda cmd: "/bin/" + cmd)
    dialog.command_edit.setText("claude -p --model sonnet")
    assert dialog.status_label.text().startswith("✓")
    assert dialog.current_settings() == {"preset": "claude-cli", "command": ["claude", "-p", "--model", "sonnet"]}


def test_anthropic_form_and_save(dialog_factory, tmp_path, monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dialog = dialog_factory(current="anthropic")
    assert not dialog.key_row.isHidden() and not dialog.model_row.isHidden()
    assert dialog.fetch_button.isHidden() and dialog.base_url_edit.isHidden()
    assert "ANTHROPIC_API_KEY" in dialog.status_label.text()
    assert dialog.model_combo.currentText() == "claude-opus-5-5"
    dialog.key_edit.setText("sk-ant-test")
    dialog.model_combo.setCurrentText("claude-sonnet-5-5")
    dialog.effort_combo.setCurrentText("medium")
    dialog.audience_edit.setText("a biologist")
    assert dialog.status_label.text().startswith("✓")
    dialog.accept()
    assert dialog.result() == dialog.DialogCode.Accepted
    saved = Config.load(tmp_path / "config.toml")
    assert saved.default_provider == "anthropic"
    assert saved.audience == "a biologist"
    assert saved.providers["anthropic"] == {
        "preset": "anthropic",
        "api_key": "sk-ant-test",
        "model": "claude-sonnet-5-5",
        "effort": "medium",
    }
    if os.name != "nt":
        assert oct((tmp_path / "config.toml").stat().st_mode & 0o777) == "0o600"


def test_save_refuses_unusable_settings(dialog_factory, tmp_path):
    dialog = dialog_factory(current="openai")
    dialog.model_combo.setCurrentText("")
    dialog.accept()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert "Cannot save yet" in dialog.result_label.text()
    assert not (tmp_path / "config.toml").exists()


def test_existing_settings_are_loaded(dialog_factory, tmp_path):
    config = Config(cache_dir=tmp_path / "cache", path=tmp_path / "config.toml")
    config.providers["ollama"] = {"preset": "ollama", "model": "llama3", "base_url": "http://box:11434/v1"}
    config.providers["mine"] = {"kind": "command", "command": ["my-llm", "--fast"]}
    dialog = dialog_factory(config, current="ollama")
    assert dialog.model_combo.currentText() == "llama3"
    assert dialog.base_url_edit.text() == "http://box:11434/v1"
    assert dialog.key_row.isHidden()  # local server: no key
    dialog.select("mine")
    assert dialog.title_label.text() == "mine (command)"
    assert dialog.command_edit.text() == "my-llm --fast"
    # an unchanged base_url equal to the preset is not stored
    dialog.select("ollama")
    dialog.base_url_edit.setText(PRESETS["ollama"]["base_url"])
    assert "base_url" not in dialog.current_settings()


def test_test_prompt(dialog_factory, qtbot, monkeypatch):
    provider = FakeProvider(explanation="OK")
    monkeypatch.setattr("paratext.reader.setup.make_provider", lambda name, settings: provider)
    dialog = dialog_factory(current="claude-cli")
    dialog.run_test()
    qtbot.waitUntil(lambda: "Success" in dialog.result_label.text(), timeout=5000)
    assert provider.calls[0]["prompt"] == "Reply with the single word OK."
    QThreadPool.globalInstance().waitForDone()


def test_fetch_models(dialog_factory, qtbot, monkeypatch):
    monkeypatch.setattr("paratext.reader.setup.list_models", lambda base_url, key: ["m-a", "m-b"])
    dialog = dialog_factory(current="custom-openai")
    assert not dialog.base_url_edit.isHidden() and not dialog.fetch_button.isHidden()
    dialog.base_url_edit.setText("http://localhost:8000/v1")
    dialog.fetch_models()
    qtbot.waitUntil(lambda: dialog.model_combo.count() == 2, timeout=5000)
    assert dialog.model_combo.currentText() == "m-a"
    assert "2 models" in dialog.result_label.text()
    assert dialog.status_label.text().startswith("✓")
    QThreadPool.globalInstance().waitForDone()


def test_initial_selection_prefers_a_ready_option(dialog_factory, monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: "/bin/gemini" if cmd == "gemini" else None)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dialog = dialog_factory()
    assert dialog.selected_name == "gemini-cli"
