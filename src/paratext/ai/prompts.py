"""Prompt templates.  Keep wording changes here so cache keys can track them."""

from __future__ import annotations

#: bump when prompt wording changes, so cached AI output is not reused
PROMPT_VERSION = 1

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


def system_prompt(audience: str) -> str:
    return (
        f"You are paraText, a reading assistant that helps {audience} understand a scientific paper. "
        "Explain terms accurately and briefly, in the sense they are used in this paper. "
        "Base explanations on the paper text you are given plus standard knowledge of the field; "
        "if the paper's specific meaning is unclear from the text, give the standard meaning and say so. "
        "Never invent results, numbers, or claims about the paper."
    )


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
