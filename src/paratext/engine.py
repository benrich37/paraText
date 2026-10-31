"""ContextEngine: builds and caches the glossary and explanations for one PDF.

GUI-independent.  AI requests run on an executor (a thread pool by default)
and report back through callbacks, which are called on the worker thread; a
GUI must marshal them to its own thread.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Callable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from pathlib import Path

from paratext.ai import prompts
from paratext.ai.providers import Provider, ProviderError
from paratext.glossary import GlossaryEntry, Span, extract_acronyms, find_spans, normalize_term, parse_terms
from paratext.pdf import PdfDocument

CACHE_VERSION = 1


class ImmediateExecutor(Executor):
    """Runs submitted work synchronously (for tests and scripts)."""

    def submit(self, fn, /, *args, **kwargs):
        future = Future()
        try:
            future.set_result(fn(*args, **kwargs))
        except BaseException as e:
            future.set_exception(e)
        return future


class ContextEngine:
    def __init__(
        self,
        doc: PdfDocument,
        provider: Provider | None,
        cache_dir=None,
        audience: str = prompts.DEFAULT_AUDIENCE,
        executor: Executor | None = None,
    ):
        self.doc = doc
        self.provider = provider
        self.audience = audience
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="paratext")
        self._lock = threading.Lock()
        self._pending: set = set()
        self.terms: dict[str, GlossaryEntry] = {}
        self.processed_pages: set[int] = set()
        self.explanations: dict[str, str] = {}
        self._load_cache()
        self._add_acronyms()

    # ------------------------------------------------------------------
    # cache
    # ------------------------------------------------------------------

    @property
    def cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        provider_key = self.provider.cache_key if self.provider else "offline"
        settings = f"{provider_key}|{self.audience}|{prompts.PROMPT_VERSION}"
        tag = hashlib.sha1(settings.encode()).hexdigest()[:10]
        return self.cache_dir / f"{self.doc.sha256[:16]}-{tag}.json"

    def _load_cache(self) -> None:
        path = self.cache_path
        if not path or not path.exists():
            return
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return
        if data.get("version") != CACHE_VERSION:
            return
        self.terms = {k: GlossaryEntry(**v) for k, v in data.get("terms", {}).items()}
        self.processed_pages = set(data.get("processed_pages", []))
        self.explanations = dict(data.get("explanations", {}))

    def save(self) -> None:
        path = self.cache_path
        if not path:
            return
        with self._lock:
            data = {
                "version": CACHE_VERSION,
                "document": str(self.doc.path),
                "provider": self.provider.cache_key if self.provider else None,
                "audience": self.audience,
                "processed_pages": sorted(self.processed_pages),
                "terms": {k: e.to_dict() for k, e in self.terms.items()},
                "explanations": self.explanations,
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
        os.replace(tmp, path)

    # ------------------------------------------------------------------
    # glossary
    # ------------------------------------------------------------------

    def _add_acronyms(self) -> None:
        for page in range(self.doc.page_count):
            for entry in extract_acronyms(self.doc.page_text(page), page):
                self.terms.setdefault(normalize_term(entry.term), entry)

    def add_entries(self, entries: list[GlossaryEntry]) -> int:
        """Merge entries; AI entries replace acronym ones but not other AI ones."""
        added = 0
        with self._lock:
            for entry in entries:
                key = normalize_term(entry.term)
                existing = self.terms.get(key)
                if existing is None or (existing.source == "acronym" and entry.source != "acronym"):
                    self.terms[key] = entry
                    added += 1
        return added

    def spans(self, page: int) -> list[Span]:
        words = [w.text for w in self.doc.words(page)]
        with self._lock:
            keys = list(self.terms)
        return find_spans(words, keys, self.doc.line_ends(page))

    def entry(self, key: str) -> GlossaryEntry | None:
        return self.terms.get(key)

    def is_page_done(self, page: int) -> bool:
        return page in self.processed_pages

    def page_job(self, page: int) -> list[GlossaryEntry]:
        """Ask the provider for the glossary of one page (blocking)."""
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        with self._lock:
            known = [e.term for e in self.terms.values() if e.source != "acronym"]
        prompt = prompts.glossary_prompt(
            self.doc.paper_context(), page + 1, self.doc.page_text(page), self.audience, known
        )
        reply = self.provider.complete(prompts.system_prompt(self.audience), prompt, prompts.GLOSSARY_SCHEMA)
        try:
            entries = parse_terms(reply, page)
        except ValueError as e:
            raise ProviderError(f"Could not read the model's glossary reply: {e}") from e
        self.add_entries(entries)
        with self._lock:
            self.processed_pages.add(page)
        self.save()
        return entries

    def ensure_page(self, page: int, callback: Callable | None = None) -> Future | None:
        """Start building page ``page``'s glossary unless it is done or running.

        ``callback(page, entries, error)`` is called when the job finishes.
        Returns the job's Future, or None if nothing was started.
        """
        key = ("page", page)
        if self.provider is None or page in self.processed_pages or key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.page_job, page)
        future.add_done_callback(lambda f: self._finish(key, f, callback, page))
        return future

    # ------------------------------------------------------------------
    # explanations of arbitrary phrases
    # ------------------------------------------------------------------

    @staticmethod
    def explanation_key(phrase: str, page: int, detailed: bool) -> str:
        return f"{'detailed' if detailed else 'brief'}|{page}|{normalize_term(phrase)}"

    def cached_explanation(self, phrase: str, page: int, detailed: bool) -> str | None:
        return self.explanations.get(self.explanation_key(phrase, page, detailed))

    def explain_job(self, phrase: str, page: int, start: int, end: int, detailed: bool) -> str:
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        prompt = prompts.explain_prompt(
            self.doc.paper_context(), phrase, self.doc.passage(page, start, end), page + 1, self.audience, detailed
        )
        text = self.provider.complete(prompts.system_prompt(self.audience), prompt).strip()
        with self._lock:
            self.explanations[self.explanation_key(phrase, page, detailed)] = text
        self.save()
        return text

    def explain(
        self, phrase: str, page: int, start: int, end: int, detailed: bool = False, callback: Callable | None = None
    ) -> Future | None:
        """Explain ``phrase`` (page words ``start..end``) in context.

        ``callback(phrase, text, error)`` is called when done (immediately if cached).
        """
        cached = self.cached_explanation(phrase, page, detailed)
        if cached is not None:
            if callback:
                callback(phrase, cached, None)
            return None
        key = ("explain", self.explanation_key(phrase, page, detailed))
        if key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.explain_job, phrase, page, start, end, detailed)
        future.add_done_callback(lambda f: self._finish(key, f, callback, phrase))
        return future

    def _finish(self, key, future: Future, callback, label) -> None:
        self._pending.discard(key)
        if callback is None:
            return
        error = future.exception()
        callback(label, None if error else future.result(), error)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
