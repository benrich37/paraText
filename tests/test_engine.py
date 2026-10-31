import json
import threading

import pytest

from paratext.ai.providers import ProviderError
from paratext.engine import ContextEngine, ImmediateExecutor
from paratext.pdf import PdfDocument
from paratext.testing import SAMPLE_GLOSSARY, FakeProvider, make_sample_pdf


@pytest.fixture
def doc(tmp_path):
    with PdfDocument(make_sample_pdf(tmp_path / "paper.pdf")) as d:
        yield d


def make_engine(doc, tmp_path, provider=None, **kw):
    return ContextEngine(doc, provider, tmp_path / "cache", executor=ImmediateExecutor(), **kw)


def test_offline_engine_has_acronyms(doc, tmp_path):
    engine = make_engine(doc, tmp_path)
    assert engine.entry("dft").source == "acronym"
    assert engine.entry("orr").explanation == "Abbreviation for “oxygen reduction reaction”."
    # acronyms defined on page 1 are found on page 2 as well
    assert "dft" in {s.key for s in engine.spans(1)}
    assert engine.ensure_page(0) is None
    with pytest.raises(ProviderError):
        engine.explain_job("DFT", 0, 10, 10, False)


def test_page_glossary_and_spans(doc, tmp_path):
    provider = FakeProvider()
    engine = make_engine(doc, tmp_path, provider)
    results = []
    engine.ensure_page(0, callback=lambda *args: results.append(args))
    assert results and results[0][0] == 0 and results[0][2] is None
    assert {e.term for e in results[0][1]} == {"oxygen reduction reaction", "limiting potential"}
    assert engine.is_page_done(0)
    keys = [s.key for s in engine.spans(0)]
    assert "oxygen reduction reaction" in keys and "limiting potential" in keys
    # the prompt carries the paper context, the page and the JSON schema
    call = provider.calls[0]
    assert "Title: A Study of Catalysis" in call["prompt"] and '<page number="1">' in call["prompt"]
    assert call["json_schema"]["required"] == ["terms"]
    # a done page is not requested again
    assert engine.ensure_page(0) is None
    assert len(provider.calls) == 1


def test_known_terms_passed_to_later_pages(doc, tmp_path):
    provider = FakeProvider()
    engine = make_engine(doc, tmp_path, provider)
    engine.ensure_page(0)
    engine.ensure_page(1)
    assert "already explained" in provider.calls[1]["prompt"]
    assert "limiting potential" in provider.calls[1]["prompt"].split("already explained")[1]
    # page 2's new term
    assert engine.entry("plane-wave basis").page == 1


def test_ai_entries_replace_acronyms(doc, tmp_path):
    provider = FakeProvider(glossary={"DFT": "A quantum-mechanical method for computing electron energies."})
    engine = make_engine(doc, tmp_path, provider)
    engine.ensure_page(0)
    assert engine.entry("dft").source == "ai"


def test_cache_round_trip(doc, tmp_path):
    provider = FakeProvider()
    engine = make_engine(doc, tmp_path, provider)
    engine.ensure_page(0)
    engine.explain("limiting potential", 0, 5, 6, detailed=True)
    path = engine.cache_path
    data = json.loads(path.read_text())
    assert data["processed_pages"] == [0]
    assert data["explanations"]

    again = FakeProvider()
    engine2 = make_engine(doc, tmp_path, again)
    assert engine2.is_page_done(0)
    assert engine2.entry("limiting potential").explanation == SAMPLE_GLOSSARY["limiting potential"]
    got = []
    engine2.explain("Limiting potential", 0, 5, 6, detailed=True, callback=lambda *a: got.append(a))
    assert got == [("Limiting potential", "A short explanation.", None)]
    assert again.calls == []


def test_cache_is_per_provider_and_audience(doc, tmp_path):
    a = make_engine(doc, tmp_path, FakeProvider())
    b = make_engine(doc, tmp_path, FakeProvider(), audience="a chemist")
    c = make_engine(doc, tmp_path, None)
    assert len({a.cache_path, b.cache_path, c.cache_path}) == 3


def test_explain_prompt_contains_passage(doc, tmp_path):
    provider = FakeProvider(explanation="  It is the potential where all steps are downhill.  ")
    engine = make_engine(doc, tmp_path, provider)
    got = []
    engine.explain("limiting potential", 0, 30, 31, callback=lambda *a: got.append(a))
    assert got == [("limiting potential", "It is the potential where all steps are downhill.", None)]
    prompt = provider.calls[0]["prompt"]
    assert "<passage>" in prompt and "sets the limiting potential" in " ".join(prompt.split())
    assert provider.calls[0]["json_schema"] is None


def test_errors_reach_callback(doc, tmp_path):
    engine = make_engine(doc, tmp_path, FakeProvider(error=ProviderError("quota exceeded")))
    got = []
    engine.ensure_page(0, callback=lambda *a: got.append(a))
    assert got[0][1] is None and "quota" in str(got[0][2])
    assert not engine.is_page_done(0)
    # a failed page can be retried
    assert engine.ensure_page(0) is not None


def test_bad_json_is_a_provider_error(doc, tmp_path):
    class Garbage(FakeProvider):
        def complete(self, system, prompt, json_schema=None):
            return "I cannot help with that."

    engine = make_engine(doc, tmp_path, Garbage())
    with pytest.raises(ProviderError, match="glossary reply"):
        engine.page_job(0)


def test_thread_pool_dedupes_inflight_requests(doc, tmp_path):
    release = threading.Event()

    class Slow(FakeProvider):
        def complete(self, *args, **kwargs):
            release.wait(5)
            return super().complete(*args, **kwargs)

    provider = Slow()
    engine = ContextEngine(doc, provider, tmp_path / "cache")
    first = engine.ensure_page(0)
    assert engine.ensure_page(0) is None
    release.set()
    first.result(timeout=5)
    engine.shutdown()
    assert len(provider.calls) == 1
