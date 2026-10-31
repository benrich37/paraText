"""Glossary data, JSON parsing of model output, and locating terms in page words."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass

# Characters stripped from the ends of words before comparing them to terms
_EDGE_PUNCT = "\"'“”‘’()[]{}<>.,;:!?*†‡§"


@dataclass
class GlossaryEntry:
    term: str
    explanation: str
    #: "ai" (model-generated), "acronym" (defined in the paper text) or "user"
    source: str = "ai"
    #: 0-based page where the entry was first found
    page: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_token(token: str) -> str:
    """Lowercase a word, expand ligatures, and strip surrounding punctuation (keeps inner hyphens)."""
    return unicodedata.normalize("NFKC", token).strip(_EDGE_PUNCT).lower()


def normalize_term(term: str) -> str:
    return " ".join(normalize_token(t) for t in term.split() if normalize_token(t))


# --------------------------------------------------------------------------
# Parsing model output
# --------------------------------------------------------------------------


def extract_json_object(text: str):
    """Parse the first JSON object/array in ``text`` (tolerates code fences and prose)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return decoder.raw_decode(text[i:])[0]
            except json.JSONDecodeError:
                continue
    raise ValueError("No JSON object found in model output")


def parse_terms(text: str, page: int | None = None) -> list[GlossaryEntry]:
    """Turn a model reply into glossary entries (invalid items are dropped)."""
    data = extract_json_object(text)
    items = data.get("terms", []) if isinstance(data, dict) else data
    entries = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        if term and explanation and normalize_term(term):
            entries.append(GlossaryEntry(term, explanation, "ai", page))
    return entries


# --------------------------------------------------------------------------
# Offline acronym detection: "long form (LF)"
# --------------------------------------------------------------------------

_ACRONYM_RE = re.compile(r"\(([A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9-]*s?)\)")


def extract_acronyms(text: str, page: int | None = None) -> list[GlossaryEntry]:
    """Find acronyms defined in the text as ``long form (ACRONYM)``.

    The long form is taken as the words immediately before the parenthesis
    whose initials spell the acronym (e.g. "density functional theory (DFT)").
    """
    text = re.sub(r"-\s*\n\s*", "", text)  # undo end-of-line hyphenation
    text = re.sub(r"\s+", " ", text)
    entries = []
    seen = set()
    for match in _ACRONYM_RE.finditer(text):
        acronym = match.group(1)
        letters = [c for c in acronym.rstrip("s") if c.isupper()]
        if len(letters) < 2 or acronym in seen:
            continue
        before = text[: match.start()].split()
        long_form = _match_long_form(before, letters)
        if long_form:
            seen.add(acronym)
            entries.append(GlossaryEntry(acronym, f"Abbreviation for “{long_form}”.", "acronym", page))
    return entries


def _match_long_form(words_before: list[str], letters: list[str]) -> str | None:
    """Walk back over at most 2*len(letters) words looking for matching initials."""
    window = words_before[-2 * len(letters) :]
    for start in range(len(window)):
        candidate = window[start:]
        parts = [p for w in candidate for p in re.split(r"[-/]", w.strip(_EDGE_PUNCT)) if p]
        initials = [p[0].upper() for p in parts if p[0].isalnum()]
        # allow small words ("of", "the", "and") that the acronym skips
        significant = [p[0].upper() for p in parts if p.lower() not in {"of", "the", "and", "for", "in", "on", "a"}]
        if initials == letters or significant == letters:
            if candidate[0].strip(_EDGE_PUNCT)[:1].upper() == letters[0]:
                return " ".join(candidate).strip(_EDGE_PUNCT + " ")
    return None


# --------------------------------------------------------------------------
# Locating terms among a page's words
# --------------------------------------------------------------------------


@dataclass
class Span:
    """A run of consecutive page words (by index) matching a glossary term."""

    key: str  # normalized term
    start: int  # first word index (inclusive)
    end: int  # last word index (inclusive)


def page_tokens(words: list[str], line_ends: set[int] | None = None) -> list[tuple[str, int, int]]:
    """Normalize page words into ``(token, first_word_idx, last_word_idx)``.

    Words that end in '-' at the end of a line are joined with the next word
    ("elec-" + "tron" -> "electron").
    """
    tokens = []
    i = 0
    line_ends = line_ends or set()
    while i < len(words):
        word = words[i]
        if word.endswith("-") and i in line_ends and i + 1 < len(words):
            tokens.append((normalize_token(word[:-1] + words[i + 1]), i, i + 1))
            i += 2
            continue
        tok = normalize_token(word)
        if tok:
            tokens.append((tok, i, i))
        i += 1
    return tokens


def find_spans(words: list[str], terms: list[str], line_ends: set[int] | None = None) -> list[Span]:
    """Locate every occurrence of each term among ``words``.

    Matching is case-insensitive and ignores surrounding punctuation.  Longer
    terms win where matches overlap.
    """
    tokens = page_tokens(words, line_ends)
    token_text = [t[0] for t in tokens]
    keys = sorted({normalize_term(t) for t in terms if normalize_term(t)}, key=lambda k: -len(k.split()))
    used = [False] * len(tokens)
    spans = []
    for key in keys:
        parts = key.split()
        n = len(parts)
        for i in range(len(tokens) - n + 1):
            if token_text[i : i + n] == parts and not any(used[i : i + n]):
                used[i : i + n] = [True] * n
                spans.append(Span(key, tokens[i][1], tokens[i + n - 1][2]))
    spans.sort(key=lambda s: s.start)
    return spans
