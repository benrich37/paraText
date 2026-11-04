"""Prompt templates.  Keep wording changes here so cache keys can track them."""

from __future__ import annotations

#: bump when prompt wording changes, so cached AI output is not reused
PROMPT_VERSION = 2

DEFAULT_AUDIENCE = "an undergraduate science student who is not a specialist in this paper's field"

GLOSSARY_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "explanation": {"type": "string"}},
                "required": ["term", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["terms"],
    "additionalProperties": False,
}


def system_prompt(audience: str, reader_profile: str = "") -> str:
    text = (
        f"You are paraText, a reading assistant that helps {audience} understand a scientific paper. "
        "Explain terms accurately and briefly, in the sense they are used in this paper. "
        "Base explanations on the paper text you are given plus standard knowledge of the field; "
        "if the paper's specific meaning is unclear from the text, give the standard meaning and say so. "
        "Never invent results, numbers, or claims about the paper."
    )
    if reader_profile:
        text += "\n\n" + reader_profile
    return text


def glossary_prompt(
    paper_context: str, page_number: int, page_text: str, audience: str, known_terms: list[str], max_terms: int = 25
) -> str:
    known = ""
    if known_terms:
        known = (
            "These terms are already explained elsewhere, so do not repeat them: "
            + "; ".join(known_terms[:150])
            + "\n\n"
        )
    return (
        "<paper_context>\n"
        f"{paper_context}\n"
        "</paper_context>\n\n"
        f'<page number="{page_number}">\n'
        f"{page_text}\n"
        "</page>\n\n"
        f"{known}"
        f"List the technical terms, acronyms, named methods, and short jargon phrases on this page that {audience} "
        "would need explained to follow the paper. Skip everyday words. Copy each term exactly as it is written "
        "on the page (same spelling, capitalization, and hyphenation) so it can be found in the text; use the "
        "shortest form that identifies it. "
        "For each term write a plain-language explanation of 1 to 3 sentences, in the sense used in this paper.\n\n"
        f'Return only a JSON object of the form {{"terms": [{{"term": "...", "explanation": "..."}}]}} '
        f"with at most {max_terms} terms, most important first."
    )


PROOFREAD_SCHEMA = {
    "type": "object",
    "properties": {
        "corrections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "action": {"type": "string", "enum": ["keep", "fix", "remove"]},
                    "explanation": {"type": "string", "description": "the corrected explanation when action is fix"},
                },
                "required": ["term", "action", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["corrections"],
    "additionalProperties": False,
}


def proofread_prompt(
    paper_context: str, page_number: int, page_text: str, entries: list[tuple[str, str]], audience: str
) -> str:
    """Re-check existing glossary entries for one page against the page text."""
    listed = "\n".join(f"- {term}: {explanation}" for term, explanation in entries)
    return (
        "<paper_context>\n"
        f"{paper_context}\n"
        "</paper_context>\n\n"
        f'<page number="{page_number}">\n'
        f"{page_text}\n"
        "</page>\n\n"
        "These glossary entries were generated earlier for terms on this page:\n"
        "<entries>\n"
        f"{listed}\n"
        "</entries>\n\n"
        f"Proofread them for {audience}. Check each entry against the page: is the term read in the sense the "
        "paper uses it (for example, a two-letter token may be a chemical element rather than an abbreviation), "
        "is the explanation correct, and is it pitched at this audience? "
        'For each entry return one object with the same "term" string and an "action": "keep" when it is right, '
        '"fix" with a corrected "explanation" (1 to 3 sentences), or "remove" when the term is not something '
        "this audience needs or the entry cannot be fixed. "
        'Return only a JSON object of the form {"corrections": [{"term": "...", "action": "...", '
        '"explanation": "..."}]}.'
    )


def explain_prompt(
    paper_context: str, phrase: str, passage: str, page_number: int, audience: str, detailed: bool
) -> str:
    if detailed:
        depth = (
            "Give a fuller explanation in one or two short paragraphs: what it means, any prerequisite idea "
            "the reader needs, and why it matters in this paper."
        )
    else:
        depth = "Answer in 1 to 3 sentences."
    return (
        "<paper_context>\n"
        f"{paper_context}\n"
        "</paper_context>\n\n"
        f'The reader highlighted "{phrase}" on page {page_number}, in this passage:\n'
        "<passage>\n"
        f"{passage}\n"
        "</passage>\n\n"
        f'Explain what "{phrase}" means here, for {audience}. {depth} '
        "Write plain text without headings or markdown."
    )


def question_prompt(paper_text: str, question: str, audience: str, truncated: bool = False, linked: str = "") -> str:
    """A free-form question about the paper as a whole, answered from its full text (plus linked files)."""
    note = (
        "(The paper is long, so only its first pages are included; say if the answer may lie in the rest.)\n\n"
        if truncated
        else ""
    )
    linked_block = (
        "The reader has linked these files to the paper (supporting information, data, folders). Use them where "
        "they hold the answer, and say which file it comes from:\n"
        "<linked_files>\n"
        f"{linked}\n"
        "</linked_files>\n\n"
        if linked
        else ""
    )
    return (
        "<paper>\n"
        f"{paper_text}\n"
        "</paper>\n\n"
        f"{note}"
        f"{linked_block}"
        "The reader asks the following question about this paper:\n"
        "<question>\n"
        f"{question}\n"
        "</question>\n\n"
        f"Answer for {audience}, using the paper's own text. Where the paper supports a claim, say where (section, "
        "figure, table or page); where it does not, say that clearly rather than guessing. Distinguish what the "
        "paper shows from what it assumes or cites. Be concise: a short paragraph or a few sentences, or a short "
        "list if the question has several parts. Write plain text without headings or markdown."
    )


def describe_link_prompt(paper_title: str, name: str, kind: str, sample: str) -> str:
    """One or two sentences saying what a linked file contains and when to consult it."""
    return (
        f'A reader of the paper "{paper_title}" linked the {kind} "{name}" to it. Here is a sample of it:\n'
        "<sample>\n"
        f"{sample}\n"
        "</sample>\n\n"
        "In one or two sentences, say what this file contains and when someone reading the paper should look at "
        "it (for example which measurements, figures, structures or data it holds). Plain text, no markdown."
    )


# --- issue reports from the reader's "Log an issue" box -------------------------------------------------------

ISSUE_SYSTEM_PROMPT = (
    "You turn a tester's quick note about the paraText PDF reader (a desktop app that underlines terms in "
    "scientific papers and explains them with an AI model) into a clear issue entry for the developer. Keep the "
    "tester's meaning exactly; do not add requirements they did not state, and do not guess at causes."
)

ISSUE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "at most 10 words, specific"},
        "category": {"type": "string", "enum": ["bug", "ui", "explanation-quality", "performance", "feature", "other"]},
        "description": {"type": "string", "description": "2 to 4 sentences: what happens, what was expected"},
    },
    "required": ["title", "category", "description"],
    "additionalProperties": False,
}


def issue_prompt(note: str, context_lines: list[str]) -> str:
    context = "\n".join(context_lines) or "(no document open)"
    return (
        "<context>\n"
        f"{context}\n"
        "</context>\n\n"
        "<note>\n"
        f"{note}\n"
        "</note>\n\n"
        "Write the issue entry: a specific title of at most 10 words, a category (bug, ui, explanation-quality, "
        "performance, feature or other) and a description of 2 to 4 sentences stating what happens and what the "
        "tester expected instead, using the context where it helps. "
        'Return only a JSON object of the form {"title": "...", "category": "...", "description": "..."}.'
    )
