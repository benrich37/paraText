"""ContextEngine: builds and caches the glossary, explanations and Q&A for one PDF.

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
from paratext.glossary import (
    GlossaryEntry,
    Span,
    extract_acronyms,
    find_spans,
    normalize_term,
    parse_corrections,
    parse_terms,
)
from paratext.links import Link, LinkStore, link_context, link_sample
from paratext.pdf import PdfDocument
from paratext.profile import UserProfile

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
        profile: UserProfile | None = None,
        link_store: LinkStore | None = None,
        allow_web: bool = False,
    ):
        self.doc = doc
        self.provider = provider
        self.audience = audience
        self.profile = profile or UserProfile()
        self.link_store = link_store
        #: the reader's permission to search the web (cited papers, literature) in questions and "More depth"
        self.allow_web = allow_web
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.executor = executor or ThreadPoolExecutor(max_workers=2, thread_name_prefix="paratext")
        self._lock = threading.Lock()
        self._pending: set = set()
        self.terms: dict[str, GlossaryEntry] = {}
        self.processed_pages: set[int] = set()
        self.explanations: dict[str, str] = {}
        self.questions: list[dict] = []  # [{"question", "answer"}] in the order asked
        self.explained: list[dict] = []  # selections the reader asked to explain: {"phrase", "page", "start", "end"}
        self._load_cache()
        self._add_acronyms()
        if self.link_store is not None:
            # links recorded under the file's hash before it was edited (e.g. highlighted in Preview) move over
            self.link_store.adopt(self.doc.sha256, self.doc.path, self.doc.title)

    # ------------------------------------------------------------------
    # cache
    # ------------------------------------------------------------------

    @property
    def cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        provider_key = self.provider.cache_key if self.provider else "offline"
        settings = f"{provider_key}|{self.audience}|{prompts.PROMPT_VERSION}|{self.profile.fingerprint()}"
        tag = hashlib.sha1(settings.encode()).hexdigest()[:10]
        return self.cache_dir / f"{self.doc.sha256[:16]}-{tag}.json"

    @staticmethod
    def _read_cache(path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) and data.get("version") == CACHE_VERSION else None

    def _stale_caches(self, path: Path) -> list[tuple[Path, dict]]:
        """Caches with these settings written for this file before it was edited, oldest first.

        Editing a PDF in place (highlights saved by Preview, for example) changes its hash and so the cache name;
        a file at the same path with the same title and page count is taken to be the same paper.
        """
        tag = path.name.split("-", 1)[1]
        needle = '"document": ' + json.dumps(str(self.doc.path.resolve()), ensure_ascii=False)
        found = []
        for other in self.cache_dir.glob(f"*-{tag}"):
            if other == path:
                continue
            try:
                with open(other, encoding="utf-8") as f:
                    head = f.read(4096)
            except OSError:
                continue
            if needle not in head:  # "document" is the second key: a cheap check before parsing
                continue
            data = self._read_cache(other)
            if data is None or data.get("title", self.doc.title) != self.doc.title:
                continue
            if data.get("pages", self.doc.page_count) != self.doc.page_count:
                continue
            if any(p >= self.doc.page_count for p in data.get("processed_pages", [])):
                continue
            found.append((other.stat().st_mtime, other, data))
        return [(other, data) for _, other, data in sorted(found, key=lambda t: t[0])]

    def _merge_cache(self, data: dict, check_words: bool) -> None:
        """Add one cache file's contents; later calls win for the same term or explanation."""
        # keyed by normalize_term(term): re-key on load so files written under an older rule still work
        for v in data.get("terms", {}).values():
            entry = GlossaryEntry(**v)
            self.terms[normalize_term(entry.term)] = entry
        self.processed_pages |= {p for p in data.get("processed_pages", []) if 0 <= p < self.doc.page_count}
        self.explanations.update(data.get("explanations", {}))
        seen = {(q["question"], q["answer"]) for q in self.questions}
        for q in data.get("questions", []):
            if "question" in q and "answer" in q and (q["question"], q["answer"]) not in seen:
                self.questions.append(q)
                seen.add((q["question"], q["answer"]))
        spots = {(e["page"], e["start"], e["end"]) for e in self.explained}
        for e in data.get("explained", []):
            if not {"phrase", "page", "start", "end"} <= set(e) or (e["page"], e["start"], e["end"]) in spots:
                continue
            if check_words and not self._phrase_at(e):
                continue  # the edit moved the words; the explanation stays reachable by selecting them again
            self.explained.append(e)
            spots.add((e["page"], e["start"], e["end"]))

    def _phrase_at(self, e: dict) -> bool:
        if not 0 <= e["page"] < self.doc.page_count:
            return False
        words = self.doc.words(e["page"])[e["start"] : e["end"] + 1]
        return normalize_term(" ".join(w.text for w in words)) == normalize_term(e["phrase"])

    def _load_cache(self) -> None:
        path = self.cache_path
        if not path:
            return
        current = self._read_cache(path) if path.exists() else None
        stale = self._stale_caches(path) if self.cache_dir.exists() else []
        for _, data in stale:
            self._merge_cache(data, check_words=True)
        if current is not None:
            self._merge_cache(current, check_words=False)
        if stale:
            self.save()
            for other, _ in stale:  # keep the old file, out of the way, rather than delete it
                try:
                    os.replace(other, other.with_name(other.name + ".adopted"))
                except OSError:
                    pass

    def save(self) -> None:
        path = self.cache_path
        if not path:
            return
        with self._lock:
            data = {
                "version": CACHE_VERSION,
                "document": str(self.doc.path.resolve()),
                "title": self.doc.title,
                "pages": self.doc.page_count,
                "provider": self.provider.cache_key if self.provider else None,
                "audience": self.audience,
                "reader_profile": self.profile.to_prompt(),
                "processed_pages": sorted(self.processed_pages),
                "terms": {k: e.to_dict() for k, e in self.terms.items()},
                "explanations": self.explanations,
                "questions": self.questions,
                "explained": self.explained,
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
        # concepts the reader already understands need no glossary entry
        known = self.profile.known + known
        prompt = prompts.glossary_prompt(
            self.doc.paper_context(), page + 1, self.doc.page_text(page), self.audience, known
        )
        reply = self.provider.complete(self.system_prompt(), prompt, prompts.GLOSSARY_SCHEMA)
        try:
            entries = parse_terms(reply, page, self.provider.cache_key)
        except ValueError as e:
            raise ProviderError(f"Could not read the model's glossary reply: {e}") from e
        self.add_entries(entries)
        with self._lock:
            self.processed_pages.add(page)
        self.save()
        return entries

    def system_prompt(self) -> str:
        return prompts.system_prompt(self.audience, self.profile.to_prompt())

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
    # proofreading existing entries with the current provider
    # ------------------------------------------------------------------

    def page_entries(self, page: int) -> list[GlossaryEntry]:
        """AI entries that occur on ``page`` (by span), whichever page first produced them."""
        with self._lock:
            terms = dict(self.terms)
        keys = {s.key for s in self.spans(page)}
        return [e for k, e in terms.items() if k in keys and e.source != "acronym"]

    def proofread_job(self, page: int) -> dict:
        """Re-check the AI entries on one page against its text (blocking). Returns counts of fixed/removed."""
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        entries = self.page_entries(page)
        counts = {"checked": len(entries), "fixed": 0, "removed": 0}
        if not entries:
            return counts
        prompt = prompts.proofread_prompt(
            self.doc.paper_context(),
            page + 1,
            self.doc.page_text(page),
            [(e.term, e.explanation) for e in entries],
            self.audience,
        )
        reply = self.provider.complete(self.system_prompt(), prompt, prompts.PROOFREAD_SCHEMA)
        try:
            corrections = parse_corrections(reply)
        except ValueError as e:
            raise ProviderError(f"Could not read the model's proofreading reply: {e}") from e
        with self._lock:
            for term, action, explanation in corrections:
                key = normalize_term(term)
                entry = self.terms.get(key)
                if entry is None or entry.source == "acronym":
                    continue
                if action == "remove":
                    del self.terms[key]
                    counts["removed"] += 1
                    continue
                if action == "fix":
                    entry.explanation = explanation
                    counts["fixed"] += 1
                entry.proofread = self.provider.cache_key
        self.save()
        return counts

    def proofread(self, page: int, callback: Callable | None = None) -> Future | None:
        """Proofread ``page`` in the background; ``callback(page, counts, error)`` when done."""
        key = ("proofread", page)
        if self.provider is None or key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.proofread_job, page)
        future.add_done_callback(lambda f: self._finish(key, f, callback, page))
        return future

    # ------------------------------------------------------------------
    # explanations of arbitrary phrases
    # ------------------------------------------------------------------

    @property
    def web_enabled(self) -> bool:
        """The reader allows web search and the provider can do it (Claude Code, the Anthropic API)."""
        return bool(self.allow_web and self.provider is not None and getattr(self.provider, "supports_web", False))

    def _complete(self, prompt: str, web: bool = False) -> str:
        if web:
            return self.provider.complete(self.system_prompt(), prompt, web=True).strip()
        return self.provider.complete(self.system_prompt(), prompt).strip()

    @staticmethod
    def explanation_key(phrase: str, page: int, detailed: bool, web: bool = False) -> str:
        kind = ("detailed" if detailed else "brief") + ("+web" if web else "")
        return f"{kind}|{page}|{normalize_term(phrase)}"

    def cached_explanation(self, phrase: str, page: int, detailed: bool, web: bool | None = None) -> str | None:
        """The cached explanation; ``web=None`` takes either kind, preferring one written with web search."""
        if web is None:
            return self.cached_explanation(phrase, page, detailed, True) or self.cached_explanation(
                phrase, page, detailed, False
            )
        return self.explanations.get(self.explanation_key(phrase, page, detailed, web))

    def explain_job(self, phrase: str, page: int, start: int, end: int, detailed: bool, web: bool = False) -> str:
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        prompt = prompts.explain_prompt(
            self.doc.paper_context(),
            phrase,
            self.doc.passage(page, start, end),
            page + 1,
            self.audience,
            detailed,
            references=self.doc.references_text() if web else "",
            web=web,
        )
        text = self._complete(prompt, web)
        with self._lock:
            self.explanations[self.explanation_key(phrase, page, detailed, web)] = text
            if not any(e["page"] == page and e["start"] == start and e["end"] == end for e in self.explained):
                self.explained.append({"phrase": phrase, "page": page, "start": start, "end": end})
        self.save()
        return text

    def explained_spans(self, page: int) -> list[dict]:
        """Selections on ``page`` that already have an explanation (so the reader can bring it back)."""
        with self._lock:
            return [dict(e) for e in self.explained if e["page"] == page]

    def explain(
        self, phrase: str, page: int, start: int, end: int, detailed: bool = False, callback: Callable | None = None
    ) -> Future | None:
        """Explain ``phrase`` (page words ``start..end``) in context.

        ``callback(phrase, text, error)`` is called when done (immediately if cached). Only "More depth"
        (``detailed``) may search the web, and only when :attr:`web_enabled`.
        """
        web = detailed and self.web_enabled
        cached = self.cached_explanation(phrase, page, detailed, web)
        if cached is not None:
            if callback:
                callback(phrase, cached, None)
            return None
        key = ("explain", self.explanation_key(phrase, page, detailed, web))
        if key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.explain_job, phrase, page, start, end, detailed, web)
        future.add_done_callback(lambda f: self._finish(key, f, callback, phrase))
        return future

    # ------------------------------------------------------------------
    # questions about the paper as a whole
    # ------------------------------------------------------------------

    @staticmethod
    def question_key(question: str) -> str:
        return " ".join(question.split()).lower()

    def linked_files(self) -> list[Link]:
        """Files the reader linked to this paper (SI PDFs, data, folders); they take part in questions."""
        return self.link_store.links(self.doc.sha256) if self.link_store else []

    def links_fingerprint(self) -> str:
        """Changes when linked files or their descriptions change, so cached answers are not reused."""
        items = sorted(f"{link.path}|{link.description}" for link in self.linked_files())
        return hashlib.sha1("\n".join(items).encode()).hexdigest()[:10] if items else ""

    def cached_answer(self, question: str, web: bool | None = None) -> str | None:
        """An earlier answer to the same question with the same linked files and web permission."""
        record = self.question_record(question, web)
        return record["answer"] if record else None

    def question_record(self, question: str, web: bool | None = None) -> dict | None:
        key = self.question_key(question)
        fingerprint = self.links_fingerprint()
        web = self.web_enabled if web is None else web
        with self._lock:
            for q in reversed(self.questions):
                if (
                    self.question_key(q["question"]) == key
                    and q.get("links", "") == fingerprint
                    and bool(q.get("web")) == web
                ):
                    return q
        return None

    def ask_job(self, question: str, web: bool = False) -> str:
        """Answer a free-form question from the whole paper's text and the linked files (blocking).

        With ``web``, the provider may also look up the papers this one cites and search the literature.
        """
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        text, truncated = self.doc.full_text()
        linked = link_context(self.linked_files())
        prompt = prompts.question_prompt(text, question, self.audience, truncated, linked, web=web)
        answer = self._complete(prompt, web)
        record = {"question": question.strip(), "answer": answer, "links": self.links_fingerprint()}
        if web:
            record["web"] = True
        with self._lock:
            self.questions.append(record)
        self.save()
        return answer

    def describe_link_job(self, link: Link) -> str:
        """Ask the provider what a linked file contains; stores it as the link's description (blocking)."""
        if self.provider is None:
            raise ProviderError("No AI provider configured.")
        prompt = prompts.describe_link_prompt(self.doc.title, link.name, link.kind, link_sample(link))
        text = self.provider.complete(self.system_prompt(), prompt).strip()
        if self.link_store is not None:
            self.link_store.set_description(self.doc.sha256, link.path, text, by=self.provider.cache_key)
        return text

    def describe_link(self, link: Link, callback: Callable | None = None) -> Future | None:
        """Describe ``link`` in the background; ``callback(link, text, error)`` when done."""
        key = ("describe", link.path)
        if self.provider is None or key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.describe_link_job, link)
        future.add_done_callback(lambda f: self._finish(key, f, callback, link))
        return future

    def ask(self, question: str, callback: Callable | None = None) -> Future | None:
        """Answer ``question`` about the paper; ``callback(question, answer, error)`` when done (at once if cached)."""
        question = question.strip()
        web = self.web_enabled
        cached = self.cached_answer(question, web)
        if cached is not None:
            if callback:
                callback(question, cached, None)
            return None
        key = ("ask", self.question_key(question), web)
        if key in self._pending:
            return None
        self._pending.add(key)
        future = self.executor.submit(self.ask_job, question, web)
        future.add_done_callback(lambda f: self._finish(key, f, callback, question))
        return future

    def _finish(self, key, future: Future, callback, label) -> None:
        self._pending.discard(key)
        if callback is None:
            return
        error = future.exception()
        callback(label, None if error else future.result(), error)

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
