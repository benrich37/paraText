"""Log issues noticed while testing the reader to a markdown file in the repo, for a later development session.

The reader's "Log an issue" box calls :func:`log_issue`. The note is kept verbatim; if an AI provider is configured
it also writes a short title, a cleaned-up description and a category, so the entry is readable without the
tester's context. The file is ``notes/ReportedIssues.md`` in the source checkout when paraText is installed
editable (the normal development setup), otherwise ``~/.config/paratext/ReportedIssues.md``; ``$PARATEXT_ISSUES``
overrides both.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paratext
from paratext.ai import prompts
from paratext.ai.providers import Provider, ProviderError
from paratext.glossary import extract_json_object

FILE_NAME = "ReportedIssues.md"
HEADER = """# Reported issues

Logged from the reader's "Log an issue" box while testing. Newest entries last. Each entry keeps the tester's
note verbatim, followed by an AI write-up when a provider was configured. Address these in a development session
and change **Status** to `done` (with the commit) or `wontfix` (with the reason).
"""


def repo_root() -> Path | None:
    """The source checkout paraText runs from, if it is installed editable (pyproject.toml above the package)."""
    for parent in Path(paratext.__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return None


def issues_path() -> Path:
    override = os.environ.get("PARATEXT_ISSUES")
    if override:
        return Path(override)
    root = repo_root()
    if root is not None:
        return root / "notes" / FILE_NAME
    return Path.home() / ".config" / "paratext" / FILE_NAME


@dataclass
class IssueContext:
    """What the reader was showing when the note was written."""

    document: str = ""
    path: str = ""
    page: int | None = None  # 1-based
    page_count: int | None = None
    provider: str = ""  # provider cache key (name, model, effort) or "none"
    audience: str = ""
    panel_title: str = ""
    extra: dict = field(default_factory=dict)

    def lines(self) -> list[str]:
        out = []
        if self.document:
            where = f" (page {self.page} of {self.page_count})" if self.page else ""
            out.append(f"Paper: {self.document}{where}, `{self.path}`")
        out.append(f"AI: {self.provider or 'none'}; audience: {self.audience or '-'}")
        if self.panel_title:
            out.append(f"Side panel showed: {self.panel_title}")
        for k, v in self.extra.items():
            out.append(f"{k}: {v}")
        return out


def ai_writeup(note: str, context: IssueContext, provider: Provider) -> dict:
    """Ask the provider for ``{"title", "category", "description"}``; raises ProviderError on failure."""
    reply = provider.complete(
        prompts.ISSUE_SYSTEM_PROMPT, prompts.issue_prompt(note, context.lines()), prompts.ISSUE_SCHEMA
    )
    try:
        data = extract_json_object(reply)
        return {
            "title": str(data["title"]).strip(),
            "category": str(data.get("category", "other")).strip(),
            "description": str(data["description"]).strip(),
        }
    except (ValueError, KeyError, TypeError) as e:
        raise ProviderError(f"Could not read the model's issue write-up: {e}") from e


def format_entry(note: str, context: IssueContext, writeup: dict | None, when: datetime, ai_note: str = "") -> str:
    title = writeup["title"] if writeup else " ".join(note.split())[:70]
    lines = [f"## {when:%Y-%m-%d %H:%M} — {title}", ""]
    if writeup:
        lines.append(f"- **Category:** {writeup['category']}")
    lines.append("- **Status:** open")
    for line in context.lines():
        lines.append(f"- {line}")
    lines += ["", "**Note (verbatim):**", "", *("> " + ln for ln in note.strip().splitlines()), ""]
    if writeup:
        lines += [f"**Write-up ({ai_note or 'AI'}):** {writeup['description']}", ""]
    elif ai_note:
        lines += [f"*No AI write-up: {ai_note}*", ""]
    return "\n".join(lines)


def append_entry(entry: str, path: Path | None = None) -> Path:
    path = path or issues_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(HEADER)
        f.write("\n" + entry)
    return path


def log_issue(
    note: str, context: IssueContext, provider: Provider | None = None, path: Path | None = None, now=None
) -> tuple[Path, str | None]:
    """Append the note (with an AI write-up when possible). Returns ``(path, ai_problem)``.

    The note is always written; a failing provider is reported in the entry and returned, never raised.
    """
    note = note.strip()
    if not note:
        raise ValueError("empty issue note")
    writeup, problem = None, None
    if provider is not None:
        try:
            writeup = ai_writeup(note, context, provider)
        except ProviderError as e:
            problem = str(e)
    ai_note = f"AI-generated by {provider.name}" if writeup else (problem or "")
    entry = format_entry(note, context, writeup, now or datetime.now(), ai_note)
    return append_entry(entry, path), problem
