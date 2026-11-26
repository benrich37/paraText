"""Development AI: a coding-agent session on paraText's own source that works through the reported issues.

The reader's "Development AI" row starts it, so the tester no longer has to switch to an editor and start a session
by hand (reported issue, 2026-11-26). It runs a command-line provider that has ``dev_args`` (Claude Code's
``claude -p --permission-mode auto``) in the source checkout, with the prompt on stdin and its output in a log file.
The process is not tied to the window: closing the reader does not stop a session halfway through an edit.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime
from pathlib import Path

from paratext.ai import prompts
from paratext.ai.providers import ProviderError
from paratext.issues import issues_path, repo_root

#: levels of the ponytail Claude Code plugin, which reads ``PONYTAIL_DEFAULT_MODE``; "" keeps its own default
PONYTAIL_LEVELS = ("", "off", "lite", "full", "ultra")


def start_session(provider, log_dir, ponytail: str = "") -> tuple[subprocess.Popen, Path]:
    """Start ``provider`` on the open reported issues; returns the process and its log file (in ``log_dir``)."""
    if provider is None:
        raise ProviderError("Choose a Development AI first.")
    if not getattr(provider, "supports_dev", False):
        raise ProviderError(f"{provider.name} cannot work on code from paraText (it has no 'dev_args').")
    root = repo_root()
    if root is None:
        raise ProviderError("The Development AI needs paraText's source checkout (an editable install).")
    prompt = prompts.dev_prompt(issues_path())
    args = provider.full_command() + list(provider.dev_args)
    if provider.prompt_via == "arg":
        args.append(prompt)
    env = dict(os.environ)
    if ponytail:
        env["PONYTAIL_DEFAULT_MODE"] = ponytail
    log_path = Path(log_dir) / f"dev-session-{datetime.now():%Y%m%d-%H%M%S}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                args,
                cwd=root,
                env=env,
                stdin=subprocess.PIPE if provider.prompt_via == "stdin" else subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
            )
    except OSError as e:  # not found, not executable
        raise ProviderError(f"{provider.name}: could not run {args[0]}: {e}") from e
    if proc.stdin:
        try:
            proc.stdin.write(prompt)
            proc.stdin.close()
        except OSError:  # it exited at once; the log says why
            pass
    return proc, log_path
