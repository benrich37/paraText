import pytest

from paratext.engine import ContextEngine, ImmediateExecutor
from paratext.pdf import PdfDocument
from paratext.profile import UserProfile
from paratext.reader.profile_dialog import ProfileDialog
from paratext.testing import FakeProvider, make_sample_pdf


def test_empty_profile():
    profile = UserProfile()
    assert profile.is_empty()
    assert profile.to_prompt() == ""
    assert profile.fingerprint() == UserProfile().fingerprint()


def test_prompt_paragraph_and_cleaning():
    profile = UserProfile(
        background="  computational   chemist, DFT user. ",
        specialties=["density functional theory", " DFT ", "density  functional theory"],
        known=["Fermi level", "fermi level", ""],
        needs_help=["Marcus theory"],
    )
    assert profile.background == "computational chemist, DFT user."
    assert profile.specialties == ["density functional theory", "DFT"]  # duplicates dropped, case-insensitively
    assert profile.known == ["Fermi level"]
    text = profile.to_prompt()
    assert text.startswith("About this reader: computational chemist, DFT user.")
    assert "do not define them): Fermi level." in text
    assert "prerequisite-first explanations whenever these come up: Marcus theory." in text
    assert profile.known_keys() == {"fermi level"}
    assert profile.fingerprint() != UserProfile().fingerprint()


def test_save_and_load(tmp_path):
    path = tmp_path / "sub" / "profile.toml"
    profile = UserProfile(background="a poet", known=["metre"], notes=[{"source": "user", "text": "likes rhyme"}])
    assert profile.save(path) == path
    assert path.read_text().startswith("# paraText reader profile")
    again = UserProfile.load(path)
    assert again.background == "a poet" and again.known == ["metre"]
    assert again.notes == [{"source": "user", "text": "likes rhyme"}]
    assert again.path == path
    missing = UserProfile.load(tmp_path / "none.toml")
    assert missing.is_empty() and missing.path == tmp_path / "none.toml"


@pytest.fixture
def doc(tmp_path):
    with PdfDocument(make_sample_pdf(tmp_path / "paper.pdf")) as d:
        yield d


def test_engine_uses_profile(doc, tmp_path):
    provider = FakeProvider()
    profile = UserProfile(background="an electrochemist", known=["oxygen reduction reaction"])
    engine = ContextEngine(doc, provider, tmp_path / "cache", executor=ImmediateExecutor(), profile=profile)
    plain = ContextEngine(doc, FakeProvider(), tmp_path / "cache", executor=ImmediateExecutor())
    assert engine.cache_path != plain.cache_path
    engine.ensure_page(0)
    call = provider.calls[0]
    assert "About this reader: an electrochemist." in call["system"]
    # known concepts are listed among the terms that need no glossary entry
    assert "oxygen reduction reaction" in call["prompt"].split("already explained elsewhere")[1].split("\n")[0]
    engine.explain("limiting potential", 0, 30, 31)
    assert "About this reader" in provider.calls[1]["system"]


def test_profile_dialog(qtbot, tmp_path):
    profile = UserProfile(background="old", known=["a"], path=tmp_path / "profile.toml")
    dialog = ProfileDialog(profile)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.background_edit.text() == "old"
    assert dialog.known_edit.toPlainText() == "a"
    dialog.background_edit.setText("new background")
    dialog.known_edit.setPlainText("a\n\nb ")
    dialog.needs_help_edit.setPlainText("c")
    assert "About this reader: new background." in dialog.preview.text()
    dialog.accept()
    assert dialog.profile.background == "new background"
    assert dialog.profile.known == ["a", "b"] and dialog.profile.needs_help == ["c"]
    assert dialog.profile.path == tmp_path / "profile.toml"
    assert profile.background == "old"  # the original is untouched until the window adopts the result


def test_reader_applies_profile(qtbot, tmp_path, monkeypatch):
    from paratext.config import Config
    from paratext.reader.app import ReaderWindow

    provider = FakeProvider()
    config = Config(cache_dir=tmp_path / "cache", path=tmp_path / "config.toml")
    config.make_provider = lambda name=None: provider
    profile = UserProfile(path=tmp_path / "profile.toml")
    window = ReaderWindow(config, make_sample_pdf(tmp_path / "p.pdf"), "fake", ImmediateExecutor(), profile=profile)
    qtbot.addWidget(window)
    window.show()
    assert "About this reader" not in provider.calls[0]["system"]

    def fake_exec(dialog):
        dialog.profile = UserProfile(background="a chemist", path=dialog.profile.path)
        return 1

    monkeypatch.setattr("paratext.reader.profile_dialog.ProfileDialog.exec", fake_exec)
    window.open_profile()
    assert (tmp_path / "profile.toml").exists()
    assert "About this reader: a chemist." in provider.calls[-1]["system"]
    assert window.engine.profile.background == "a chemist"
