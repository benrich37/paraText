"""The reader profile: a local, user-editable record of what the reader knows.

See ``notes/user_profile_design.md``.  v1 holds what the user declares; the
model never writes to it.
"""

from __future__ import annotations

import hashlib
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from paratext.glossary import normalize_term

PROFILE_TEMPLATE_HELP = """\
# paraText reader profile.  Everything here is written for the AI model so it can
# pitch explanations at you; edit freely (or use "About you…" in the reader).
"""


def default_profile_path() -> Path:
    return Path(os.environ.get("PARATEXT_PROFILE", Path.home() / ".config" / "paratext" / "profile.toml"))


def _clean_list(items) -> list[str]:
    seen = set()
    out = []
    for item in items or []:
        text = " ".join(str(item).split())
        key = normalize_term(text)
        if key and key not in seen:
            seen.add(key)
            out.append(text)
    return out


@dataclass
class UserProfile:
    #: one or two sentences in the reader's words (field, level, what they work on)
    background: str = ""
    #: areas the reader knows deeply; their vocabulary can be used freely
    specialties: list[str] = field(default_factory=list)
    #: concepts that need no explanation
    known: list[str] = field(default_factory=list)
    #: concepts to explain carefully, prerequisites first
    needs_help: list[str] = field(default_factory=list)
    #: free-form observations with provenance (reserved for inferred entries)
    notes: list[dict] = field(default_factory=list)
    path: Path | None = None

    def __post_init__(self):
        self.background = " ".join(self.background.split())
        self.specialties = _clean_list(self.specialties)
        self.known = _clean_list(self.known)
        self.needs_help = _clean_list(self.needs_help)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path=None) -> UserProfile:
        path = Path(path) if path else default_profile_path()
        if not path.exists():
            return cls(path=path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls(
            background=data.get("background", ""),
            specialties=data.get("specialties", []),
            known=data.get("known", []),
            needs_help=data.get("needs_help", []),
            notes=list(data.get("notes", [])),
            path=path,
        )

    def save(self, path=None) -> Path:
        path = Path(path) if path else (self.path or default_profile_path())
        data = {k: v for k, v in asdict(self).items() if k != "path"}
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(PROFILE_TEMPLATE_HELP + tomli_w.dumps(data))
        os.replace(tmp, path)
        self.path = path
        return path

    # ------------------------------------------------------------------
    # use in prompts
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        return not (self.background or self.specialties or self.known or self.needs_help)

    def known_keys(self) -> set[str]:
        return {normalize_term(k) for k in self.known}

    def to_prompt(self) -> str:
        """One paragraph about the reader for the system prompt ('' if nothing is set)."""
        parts = []
        if self.background:
            parts.append(f"About this reader: {self.background.rstrip('.')}.")
        if self.specialties:
            parts.append(
                "They know these areas deeply, so use their vocabulary freely: " + "; ".join(self.specialties) + "."
            )
        if self.known:
            parts.append("They already understand these concepts (do not define them): " + "; ".join(self.known) + ".")
        if self.needs_help:
            parts.append(
                "They have asked for careful, prerequisite-first explanations whenever these come up: "
                + "; ".join(self.needs_help)
                + "."
            )
        return " ".join(parts)

    def fingerprint(self) -> str:
        """Short hash of everything that reaches the prompts (part of the cache key)."""
        return hashlib.sha1(self.to_prompt().encode()).hexdigest()[:10]
