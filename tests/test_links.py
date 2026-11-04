"""Files linked to a paper (SI PDFs, data, folders)."""

import json

import pytest

from paratext.links import LinkStore, default_links_path, kind_of


def test_store_round_trip(tmp_path):
    store = LinkStore(tmp_path / "links.json")
    si = tmp_path / "si.pdf"
    si.write_bytes(b"%PDF")
    data = tmp_path / "data.csv"
    data.write_text("a,b")
    folder = tmp_path / "raw"
    folder.mkdir()
    assert store.links("abc") == []
    store.add("abc", si, doc_path="/p/paper.pdf")
    store.add("abc", data)
    store.add("abc", folder)
    kinds = [(link.kind, link.name) for link in store.links("abc")]
    assert kinds == [("pdf", "si.pdf"), ("data", "data.csv"), ("folder", "raw")]
    assert all(link.exists and link.added for link in store.links("abc"))
    # re-linking the same path does not duplicate it
    store.add("abc", si, label="Supporting information")
    links = store.links("abc")
    assert len(links) == 3 and links[-1].name == "Supporting information"
    # persisted, keyed by document hash
    again = LinkStore(tmp_path / "links.json")
    assert [link.path for link in again.links("abc")] == [link.path for link in links]
    assert json.loads((tmp_path / "links.json").read_text())["documents"]["abc"]["document"] == "/p/paper.pdf"
    assert again.remove("abc", data) and not again.remove("abc", data)
    assert [link.kind for link in again.links("abc")] == [link.kind for link in links if link.kind != "data"]
    with pytest.raises(ValueError):
        store.add("abc", si, kind="movie")


def test_kind_and_default_path(tmp_path, monkeypatch):
    assert kind_of(tmp_path) == "folder" and kind_of("x.PDF") == "pdf" and kind_of("x.xlsx") == "data"
    monkeypatch.setenv("PARATEXT_LINKS", str(tmp_path / "l.json"))
    assert default_links_path() == tmp_path / "l.json"
    missing = LinkStore(tmp_path / "nope.json")
    assert missing.links("x") == []
