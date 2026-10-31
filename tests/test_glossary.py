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
    assert tokens[1][1:] == (1, 2)


def test_find_spans():
    words = "The Oxygen reduction reaction (ORR) sets the limiting potential. ORR again, and reduction.".split()
    spans = find_spans(words, ["oxygen reduction reaction", "ORR", "reduction", "limiting potential"])
    got = [(s.key, s.start, s.end) for s in spans]
    assert got == [
        ("oxygen reduction reaction", 1, 3),
        ("orr", 4, 4),
        ("limiting potential", 7, 8),
        ("orr", 9, 9),
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
