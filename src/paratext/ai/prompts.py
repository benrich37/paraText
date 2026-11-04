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


def question_prompt(paper_text: str, question: str, audience: str, truncated: bool = False) -> str:
    """A free-form question about the paper as a whole, answered from its full text."""
    note = (
        "(The paper is long, so only its first pages are included; say if the answer may lie in the rest.)\n\n"
        if truncated
        else ""
    )
    return (
        "<paper>\n"
        f"{paper_text}\n"
        "</paper>\n\n"
        f"{note}"
        "The reader asks the following question about this paper:\n"
        "<question>\n"
        f"{question}\n"
        "</question>\n\n"
        f"Answer for {audience}, using the paper's own text. Where the paper supports a claim, say where (section, "
        "figure, table or page); where it does not, say that clearly rather than guessing. Distinguish what the "
        "paper shows from what it assumes or cites. Be concise: a short paragraph or a few sentences, or a short "
        "list if the question has several parts. Write plain text without headings or markdown."
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
