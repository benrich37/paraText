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
