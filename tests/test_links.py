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


def test_pdf_links_are_bidirectional(tmp_path):
    from paratext.links import file_sha256
    from paratext.testing import make_sample_pdf

    main = make_sample_pdf(tmp_path / "main.pdf", title="Main")
    si = make_sample_pdf(tmp_path / "si.pdf", title="SI")
    store = LinkStore(tmp_path / "links.json")
    store.add(file_sha256(main), si, "pdf", doc_path=str(main))
    back = store.links(file_sha256(si))
    assert [(link.kind, link.path) for link in back] == [("pdf", str(main.resolve()))]
    # data links are one-way (a csv has no link list); unlinking the SI removes the reverse link too
    store.add(file_sha256(main), tmp_path / "links.json", "data", doc_path=str(main))
    assert store.remove(file_sha256(main), si)
    assert store.links(file_sha256(si)) == [] and [link.kind for link in store.links(file_sha256(main))] == ["data"]


def test_descriptions_and_link_context(tmp_path):
    from paratext.links import link_context, link_sample
    from paratext.testing import make_sample_pdf

    si = make_sample_pdf(tmp_path / "si.pdf", title="Supporting Information")
    csv = tmp_path / "adsorption.csv"
    csv.write_text("facet,energy\n(001),-1.2\n")
    folder = tmp_path / "raw"
    folder.mkdir()
    (folder / "run1.out").write_text("x")
    blob = tmp_path / "image.tif"
    blob.write_bytes(b"\x00" * 10)
    store = LinkStore(tmp_path / "links.json")
    for path in (si, csv, folder, blob, tmp_path / "gone.csv"):
        store.add("abc", path)
    assert store.set_description("abc", csv, "  Adsorption energies per facet. ")
    assert not store.set_description("abc", tmp_path / "other.csv", "x")
    links = store.links("abc")
    assert links[1].description == "Adsorption energies per facet." and links[1].description_by == "user"
    # re-linking keeps the description
    store.add("abc", csv)
    assert store.links("abc")[-1].description == "Adsorption energies per facet."
    text = link_context(store.links("abc"))
    assert '<linked_file kind="pdf" name="si.pdf"' in text and "Title: Supporting Information" in text
    assert '<page number="1">' in text and "DFT" in text
    assert "Description: Adsorption energies per facet.\nfacet,energy\n(001),-1.2" in text
    assert "Folder contents:\nrun1.out" in text
    assert "tif file, 10 bytes; contents not included" in text
    assert "(file not found)" in text
    assert "(omitted: no room)" in link_context(store.links("abc"), max_chars=50)
    assert "facet,energy" in link_sample(links[1]) and "Title: Supporting Information" in link_sample(links[0])
