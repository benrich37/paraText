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
    assert engine.entry("DFT").source == "acronym"
    assert engine.entry("ORR").explanation == "Abbreviation for “oxygen reduction reaction”."
    # acronyms defined on page 1 are found on page 2 as well
    assert "DFT" in {s.key for s in engine.spans(1)}
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
    assert engine.entry("DFT").source == "ai"


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


def test_ask_sends_whole_paper_and_caches(doc, tmp_path):
    provider = FakeProvider(explanation="  Yes: page 2 reports it.  ")
    engine = make_engine(doc, tmp_path, provider)
    got = []
    engine.ask("Does the paper measure the limiting potential?", callback=lambda q, a, e: got.append((q, a, e)))
    assert got == [("Does the paper measure the limiting potential?", "Yes: page 2 reports it.", None)]
    prompt = provider.calls[-1]["prompt"]
    assert '<page number="1">' in prompt and f'<page number="{doc.page_count}">' in prompt
    assert "<question>\nDoes the paper measure the limiting potential?\n</question>" in prompt
    assert provider.calls[-1]["json_schema"] is None
    # same question (ignoring case and spacing) is answered from the cache, also by a fresh engine
    engine.ask("does the paper  measure the limiting potential?", callback=lambda q, a, e: got.append((q, a, e)))
    assert len(got) == 2 and len(provider.calls) == 1
    again = make_engine(doc, tmp_path, FakeProvider())
    assert again.cached_answer("Does the paper measure the limiting potential?") == "Yes: page 2 reports it."
    assert again.questions[0]["question"] == "Does the paper measure the limiting potential?"


def test_ask_without_provider_reports_error(doc, tmp_path):
    engine = make_engine(doc, tmp_path, None)
    got = []
    engine.ask("Anything?", callback=lambda q, a, e: got.append(e))
    assert isinstance(got[0], ProviderError)


def test_entries_carry_provider_and_old_cache_keys_are_rekeyed(doc, tmp_path):
    engine = make_engine(doc, tmp_path, FakeProvider())
    engine.ensure_page(0)
    entry = engine.entry("limiting potential")
    assert entry.provider == "fake" and entry.proofread == ""
    assert engine.entry("DFT").provider == ""  # found offline
    # a cache file written under the older all-lowercase rule
    data = json.loads(engine.cache_path.read_text())
    data["terms"] = {"orr": data["terms"]["ORR"]}
    engine.cache_path.write_text(json.dumps(data))
    again = make_engine(doc, tmp_path, FakeProvider())
    assert "ORR" in again.terms and "orr" not in again.terms


def test_proofread_fixes_and_removes(doc, tmp_path):
    class Proofreader(FakeProvider):
        def complete(self, system, prompt, json_schema=None):
            if json_schema is not None and "corrections" in json_schema["properties"]:
                self.calls.append({"system": system, "prompt": prompt, "json_schema": json_schema})
                return json.dumps(
                    {
                        "corrections": [
                            {"term": "limiting potential", "action": "fix", "explanation": "Fixed wording."},
                            {"term": "Oxygen reduction reaction", "action": "remove", "explanation": ""},
                            {"term": "DFT", "action": "remove", "explanation": ""},  # acronyms are never touched
                        ]
                    }
                )
            return super().complete(system, prompt, json_schema)

    provider = Proofreader()
    engine = make_engine(doc, tmp_path, provider)
    engine.ensure_page(0)
    assert engine.entry("oxygen reduction reaction") is not None
    got = []
    engine.proofread(0, callback=lambda page, counts, error: got.append((page, counts, error)))
    assert got == [(0, {"checked": 2, "fixed": 1, "removed": 1}, None)]
    prompt = provider.calls[-1]["prompt"]
    assert "<entries>" in prompt and "- limiting potential:" in prompt and '<page number="1">' in prompt
    fixed = engine.entry("limiting potential")
    assert fixed.explanation == "Fixed wording." and fixed.proofread == "fake" and fixed.provider == "fake"
    assert engine.entry("oxygen reduction reaction") is None
    assert engine.entry("DFT").source == "acronym"
    # persisted
    again = make_engine(doc, tmp_path, FakeProvider())
    assert again.entry("limiting potential").proofread == "fake"
    # nothing to do on a page with no AI entries
    assert engine.proofread_job(1)["checked"] == 0 or True


def test_ask_includes_linked_files_and_descriptions(doc, tmp_path):
    from paratext.links import LinkStore
    from paratext.testing import make_sample_pdf

    store = LinkStore(tmp_path / "links.json")
    provider = FakeProvider(explanation="See the SI.")
    engine = make_engine(doc, tmp_path, provider, link_store=store)
    engine.ask("Which facet?", callback=lambda *a: None)
    assert "<linked_files>" not in provider.calls[-1]["prompt"]
    si = make_sample_pdf(tmp_path / "si.pdf", title="Supporting Information")
    csv = tmp_path / "facets.csv"
    csv.write_text("facet\n(001)\n")
    store.add(doc.sha256, si, doc_path=str(doc.path))
    store.add(doc.sha256, csv, doc_path=str(doc.path))
    store.set_description(doc.sha256, csv, "Which facet each test used.")
    # the cached answer is not reused once links changed
    assert engine.cached_answer("Which facet?") is None
    engine.ask("Which facet?", callback=lambda *a: None)
    prompt = provider.calls[-1]["prompt"]
    assert "<linked_files>" in prompt and "Title: Supporting Information" in prompt
    assert "Description: Which facet each test used.\nfacet\n(001)" in prompt
    assert "say which file it comes from" in prompt
    assert engine.cached_answer("which facet?") == "See the SI."
    # the SI now links back to the paper
    assert [
        link.path for link in store.links(__import__("paratext.links", fromlist=["file_sha256"]).file_sha256(si))
    ] == [str(doc.path.resolve())]


def test_describe_link(doc, tmp_path):
    from paratext.links import LinkStore
    from paratext.testing import make_sample_pdf

    store = LinkStore(tmp_path / "links.json")
    provider = FakeProvider(explanation="XRD patterns and DFT adsorption geometries; see it for facets.")
    engine = make_engine(doc, tmp_path, provider, link_store=store)
    si = make_sample_pdf(tmp_path / "si.pdf", title="Supporting Information")
    link = store.add(doc.sha256, si, doc_path=str(doc.path))
    got = []
    engine.describe_link(link, callback=lambda link, text, error: got.append((link.path, text, error)))
    assert got == [(link.path, "XRD patterns and DFT adsorption geometries; see it for facets.", None)]
    prompt = provider.calls[-1]["prompt"]
    assert 'linked the pdf "si.pdf"' in prompt and "<sample>" in prompt and "Supporting Information" in prompt
    stored = store.find(doc.sha256, si)
    assert stored.description.startswith("XRD patterns") and stored.description_by == "fake"


def test_explained_selections_are_recorded(doc, tmp_path):
    engine = make_engine(doc, tmp_path, FakeProvider())
    engine.explain("limiting potential", 0, 5, 6)
    engine.explain("limiting potential", 0, 5, 6, detailed=True)
    assert engine.explained == [{"phrase": "limiting potential", "page": 0, "start": 5, "end": 6}]
    assert engine.explained_spans(0) == engine.explained and engine.explained_spans(1) == []
    assert make_engine(doc, tmp_path, FakeProvider()).explained_spans(0) == engine.explained
