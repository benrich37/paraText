import pytest

from paratext.pdf import PdfDocument
from paratext.testing import make_sample_pdf


@pytest.fixture
def doc(tmp_path):
    with PdfDocument(make_sample_pdf(tmp_path / "paper.pdf")) as d:
        yield d


def test_basic_properties(doc):
    assert doc.page_count == 2
    assert doc.title == "A Study of Catalysis"
    assert doc.page_size(0) == (420, 300)
    assert len(doc.sha256) == 64


def test_words_have_boxes_in_reading_order(doc):
    words = doc.words(0)
    assert [w.text for w in words[:4]] == ["A", "Study", "of", "Catalysis"]
    assert all(w.x1 > w.x0 and w.y1 > w.y0 for w in words)
    assert words[0].y0 < words[-1].y0


def test_line_ends(doc):
    words = doc.words(0)
    ends = doc.line_ends(0)
    assert 3 in ends  # "Catalysis" ends the title line
    assert len(words) - 1 in ends
    for i in ends:
        if i + 1 < len(words):
            assert (words[i].block, words[i].line) != (words[i + 1].block, words[i + 1].line)


def test_word_at(doc):
    w = doc.words(0)[1]
    assert doc.word_at(0, (w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2) == 1
    assert doc.word_at(0, 1, 1) is None


def test_text_context_and_passage(doc):
    assert "density functional theory" in " ".join(doc.page_text(0).split())
    assert doc.paper_context().startswith("Title: A Study of Catalysis")
    assert doc.passage(0, 1, 1, radius=1) == "A Study of"


def test_render_png(doc):
    png = doc.render_png(0, zoom=1.5)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_full_text_wraps_pages_and_truncates(tmp_path):
    doc = PdfDocument(make_sample_pdf(tmp_path / "p.pdf"))
    text, truncated = doc.full_text()
    assert not truncated
    assert text.count("<page number=") == doc.page_count and "DFT" in text
    short, truncated = doc.full_text(max_chars=10)
    assert truncated and short.count("<page number=") == 1  # at least the first page is always included
    doc.close()


def test_references_text(tmp_path):
    from paratext.testing import SAMPLE_PAGES, make_sample_pdf

    refs = "Acknowledgements. Thanks.\nReferences\n[1] A. Author, A title, J. 1 (2020) 1."
    with PdfDocument(make_sample_pdf(tmp_path / "a.pdf", pages=[*SAMPLE_PAGES, refs, "[2] B. Author, More."])) as d:
        text = d.references_text()
        assert text.startswith("References\n[1] A. Author") and "[2] B. Author" in text
        assert "Thanks" not in text and len(d.references_text(max_chars=20)) == 20
    with PdfDocument(make_sample_pdf(tmp_path / "b.pdf")) as d:
        assert d.references_text() == ""  # "references" inside a sentence is not a heading
