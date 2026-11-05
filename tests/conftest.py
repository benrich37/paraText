"""Shared fixtures for paraText tests."""

from __future__ import annotations

import os

# Qt tests run without a display; must be set before a QApplication exists
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import _tkinter  # noqa: E402
import tkinter as tk  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

TEST_DIR = Path(__file__).absolute().parent
REPO_DIR = TEST_DIR.parent


def pump_events(root: tk.Tk) -> None:
    """Process all pending Tk events without entering mainloop."""
    while root.dooneevent(_tkinter.ALL_EVENTS | _tkinter.DONT_WAIT):
        pass


@pytest.fixture
def tk_root():
    """A Tk root window; tests using it are skipped when there is no display."""
    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"no display available for Tk: {e}")
    root.geometry("440x100")
    yield root
    root.destroy()


@pytest.fixture(autouse=True)
def _isolated_links(tmp_path, monkeypatch):
    """Never touch the user's real ~/.config/paratext/links.json (or the saved pane sizes) from tests."""
    monkeypatch.setenv("PARATEXT_LINKS", str(tmp_path / "links.json"))
    monkeypatch.setenv("PARATEXT_UI_STATE", str(tmp_path / "ui.ini"))
