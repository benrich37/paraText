import pytest

from paratext.glossary import (
    GlossaryEntry,
    extract_acronyms,
    extract_json_object,
    find_spans,
    normalize_term,
    page_tokens,
    parse_terms,
)


@pytest.mark.parametrize(
    "text",
    [
        '{"terms": [{"term": "DFT", "explanation": "x"}]}',
        '```json\n{"terms": [{"term": "DFT", "explanation": "x"}]}\n```',
        'Sure! Here it is: {"terms": [{"term": "DFT", "explanation": "x"}]} Hope that helps.',
    ],
)
def test_extract_json_object(text):
    assert extract_json_object(text)["terms"][0]["term"] == "DFT"


def test_extract_json_object_none():
    with pytest.raises(ValueError):
        extract_json_object("no json here")


def test_parse_terms_drops_bad_items():
    reply = '{"terms": [{"term": "DFT", "explanation": "x"}, {"term": "", "explanation": "y"}, "junk", {"term": "a"}]}'
    assert parse_terms(reply, page=2) == [GlossaryEntry("DFT", "x", "ai", 2)]


def test_parse_terms_bare_list():
    assert parse_terms('[{"term": "ORR", "explanation": "x"}]')[0].term == "ORR"


def test_normalize_term():
    assert normalize_term("  (Density  Functional Theory), ") == "density functional theory"
    assert normalize_term("plane-wave") == "plane-wave"
    # short capitalized tokens keep their case: Faradaic efficiency and iron are different terms
    assert normalize_term("FE") == "FE" and normalize_term("Fe") == "Fe" and normalize_term("(pH)") == "pH"
    assert normalize_term("fe") == "fe" and normalize_term("NiMnO2") == "nimno2"


def test_short_capitalized_terms_match_case_sensitively():
    words = "The FE of Fe sites was 90%; the FE rose, and fe is not a word.".split()
    spans = find_spans(words, ["FE", "Fe"])
    assert [(s.key, s.start) for s in spans] == [("FE", 1), ("Fe", 3), ("FE", 8)]
    # a lowercase term still matches any case
    assert [(s.key, s.start) for s in find_spans(words, ["fe"])] == [("fe", 1), ("fe", 3), ("fe", 8), ("fe", 11)]


def test_parse_corrections():
    from paratext.glossary import parse_corrections

    text = """{"corrections": [
        {"term": "FE", "action": "keep", "explanation": ""},
        {"term": "Fe", "action": "fix", "explanation": "The chemical symbol for iron."},
        {"term": "the", "action": "remove", "explanation": ""},
        {"term": "x", "action": "fix", "explanation": ""},
        {"term": "", "action": "keep"}, {"term": "y", "action": "maybe"}]}"""
    assert parse_corrections(text) == [
        ("FE", "keep", ""),
        ("Fe", "fix", "The chemical symbol for iron."),
        ("the", "remove", ""),
    ]


def test_extract_acronyms():
    text = (
        "We use density functional theory (DFT) and the oxygen reduction reaction (ORR). "
        "Self-consistent field (SCF) loops, the Brillouin zone (BZ), and a random thing (XYZ)."
    )
    found = {e.term: e.explanation for e in extract_acronyms(text, page=0)}
    assert found["DFT"] == "Abbreviation for “density functional theory”."
    assert found["ORR"] == "Abbreviation for “oxygen reduction reaction”."
    assert found["SCF"] == "Abbreviation for “Self-consistent field”."
    assert found["BZ"] == "Abbreviation for “Brillouin zone”."
    assert "XYZ" not in found


def test_extract_acronyms_skips_small_words_and_hyphenation():
    text = "the potential of zero charge (PZC) and the hydrogen evo-\nlution reaction (HER)"
    found = {e.term: e.explanation for e in extract_acronyms(text)}
    assert found["PZC"] == "Abbreviation for “potential of zero charge”."
    assert found["HER"] == "Abbreviation for “hydrogen evolution reaction”."


def test_page_tokens_joins_line_end_hyphens():
    words = ["the", "elec-", "tron", "is", "self-", "consistent"]
    tokens = page_tokens(words, line_ends={1})
    assert [t[0] for t in tokens] == ["the", "electron", "is", "self-", "consistent"]
    assert tokens[1][1:3] == (1, 2) and tokens[1][3] == "electron"


def test_find_spans():
    words = "The Oxygen reduction reaction (ORR) sets the limiting potential. ORR again, and reduction.".split()
    spans = find_spans(words, ["oxygen reduction reaction", "ORR", "reduction", "limiting potential"])
    got = [(s.key, s.start, s.end) for s in spans]
    assert got == [
        ("oxygen reduction reaction", 1, 3),
        ("ORR", 4, 4),
        ("limiting potential", 7, 8),
        ("ORR", 9, 9),
        ("reduction", 12, 12),
    ]


def test_find_spans_across_hyphenated_line_break():
    words = ["an", "elec-", "trode", "here"]
    spans = find_spans(words, ["electrode"], line_ends={1})
    assert [(s.start, s.end) for s in spans] == [(1, 2)]


def test_ligatures_match_plain_terms():
    assert normalize_term("selective-area electron diﬀraction") == "selective-area electron diffraction"
    spans = find_spans(["the", "Deﬁnitive", "proof"], ["definitive proof"])
    assert [(s.start, s.end) for s in spans] == [(1, 2)]
