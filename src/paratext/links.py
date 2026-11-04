"""Files linked to a paper: supporting-information PDFs, data files and folders.

Links are user data, not cache, so they live in the config directory (``$PARATEXT_LINKS`` or
``~/.config/paratext/links.json``), keyed by the paper's SHA-256 so they survive moving or renaming the PDF.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

KINDS = ("pdf", "data", "folder")


def default_links_path() -> Path:
    return Path(os.environ.get("PARATEXT_LINKS", Path.home() / ".config" / "paratext" / "links.json"))


@dataclass
class Link:
    path: str
    kind: str = "data"  # "pdf", "data" or "folder"
    label: str = ""
    added: str = ""

    @property
    def exists(self) -> bool:
        return Path(self.path).exists()

    @property
    def name(self) -> str:
        return self.label or Path(self.path).name


def kind_of(path) -> str:
    p = Path(path)
    if p.is_dir():
        return "folder"
    return "pdf" if p.suffix.lower() == ".pdf" else "data"


class LinkStore:
    """All links, keyed by document hash; saved on every change."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or default_links_path())
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        docs = raw.get("documents", {}) if isinstance(raw, dict) else {}
        self._data = {k: v for k, v in docs.items() if isinstance(v, dict)}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"version": 1, "documents": self._data}, indent=1, ensure_ascii=False))
        os.replace(tmp, self.path)

    def links(self, doc_hash: str) -> list[Link]:
        return [Link(**item) for item in self._data.get(doc_hash, {}).get("links", [])]

    def add(self, doc_hash: str, path, kind: str | None = None, doc_path: str = "", label: str = "") -> Link:
        """Link ``path`` to the document; re-linking an existing path updates it instead of duplicating."""
        path = str(Path(path).expanduser().resolve())
        kind = kind or kind_of(path)
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, not {kind!r}")
        entry = self._data.setdefault(doc_hash, {"document": doc_path, "links": []})
        if doc_path:
            entry["document"] = doc_path
        link = Link(path, kind, label, datetime.now().isoformat(timespec="minutes"))
        entry["links"] = [item for item in entry["links"] if item.get("path") != path] + [asdict(link)]
        self.save()
        return link

    def remove(self, doc_hash: str, path) -> bool:
        path = str(Path(path).expanduser().resolve())
        entry = self._data.get(doc_hash)
        if not entry:
            return False
        before = len(entry["links"])
        entry["links"] = [item for item in entry["links"] if item.get("path") != path]
        if not entry["links"]:
            del self._data[doc_hash]
        self.save()
        return len(entry["links"]) != before
