"""Tests for the Development AI session (a coding agent the reader runs on the reported issues)."""

import sys

import pytest

from paratext.ai.providers import CommandProvider, ProviderError, make_provider
from paratext.dev import start_session
from paratext.issues import repo_root

# stands in for `claude -p --permission-mode auto`: reports its arguments, folder, ponytail level and prompt
AGENT = (
    "import os, sys; print('args', sys.argv[1:]); print('cwd', os.getcwd()); "
    "print('ponytail', os.environ.get('PONYTAIL_DEFAULT_MODE')); print(sys.stdin.read())"
)

needs_checkout = pytest.mark.skipif(repo_root() is None, reason="needs the source checkout (editable install)")


@needs_checkout
def test_session_runs_the_agent_in_the_checkout(tmp_path, monkeypatch):
    monkeypatch.delenv("PONYTAIL_DEFAULT_MODE", raising=False)
    agent = CommandProvider(command=[sys.executable, "-c", AGENT], dev_args=["--dev"], name="agent")
    proc, log = start_session(agent, tmp_path, ponytail="lite")
    assert proc.wait(60) == 0 and log.parent == tmp_path
    out = log.read_text(encoding="utf-8")
    assert "args ['--dev']" in out and str(repo_root()) in out and "ponytail lite" in out
    assert "Status: open" in out and "ReportedIssues.md" in out and "Do not commit" in out  # the prompt, on stdin
    # no level: the plugin keeps its own default
    proc, log = start_session(agent, tmp_path)
    proc.wait(60)
    assert "ponytail None" in log.read_text(encoding="utf-8")


def test_session_needs_an_agent_that_can_edit_code(tmp_path):
    with pytest.raises(ProviderError, match="cannot work on code"):
        start_session(CommandProvider(command=["my-llm"], name="plain"), tmp_path)
    with pytest.raises(ProviderError, match="Choose a Development AI"):
        start_session(None, tmp_path)


def test_claude_cli_can_work_on_code():
    claude = make_provider("claude-cli", {"model": "opus"})
    assert claude.supports_dev and claude.dev_args == ["--permission-mode", "auto"]
    assert "permission-mode" not in claude.cache_key  # explanations cached with it stay valid
    assert not make_provider("codex-cli").supports_dev
