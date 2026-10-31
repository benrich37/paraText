"""Shared fixtures for paraText tests."""

from __future__ import annotations

import _tkinter
import tkinter as tk
from pathlib import Path

import pytest

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
