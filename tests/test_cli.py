import json
import sys

import pytest

from paratext.cli import main, parse_pages
from paratext.testing import make_sample_pdf

# A stand-in "subscription CLI": reads the prompt on stdin and answers like a model would.
FAKE_LLM = r"""
import json, sys
prompt = sys.stdin.read()
if "Return only a JSON object" in prompt:
    page = prompt.split("</page>")[0]
    terms = []
    if "limiting potential" in " ".join(page.split()):
        terms.append({"term": "limiting potential", "explanation": "Where every step becomes downhill."})
    print(json.dumps({"terms": terms}))
else:
    print("Explained in context.")
"""


@pytest.fixture
def setup(tmp_path, monkeypatch):
    script = tmp_path / "fake_llm.py"
    script.write_text(FAKE_LLM)
    config = tmp_path / "config.toml"
    command = json.dumps([sys.executable, str(script)])
    config.write_text(f'default_provider = "fake"\n[providers.fake]\nkind = "command"\ncommand = {command}\n')
    monkeypatch.setenv("PARATEXT_CACHE_DIR", str(tmp_path / "cache"))
    return tmp_path, str(config), str(make_sample_pdf(tmp_path / "paper.pdf"))


def test_parse_pages():
    assert parse_pages(None, 3) == [0, 1, 2]
    assert parse_pages("1,3-4", 5) == [0, 2, 3]
    with pytest.raises(SystemExit):
        parse_pages("9", 3)


def test_glossary_json(setup, capsys):
    _, config, pdf = setup
    assert main(["--config", config, "glossary", pdf, "--json"]) == 0
    entries = {e["term"]: e for e in json.loads(capsys.readouterr().out)}
    assert entries["limiting potential"]["source"] == "ai"
    assert entries["DFT"]["source"] == "acronym"


def test_glossary_offline(setup, capsys):
    _, config, pdf = setup
    assert main(["--config", config, "glossary", pdf, "--provider", "none"]) == 0
    out = capsys.readouterr()
    assert "DFT" in out.out and "acronyms" in out.err


def test_explain(setup, capsys):
    _, config, pdf = setup
    assert main(["--config", config, "explain", pdf, "limiting potential", "--page", "1"]) == 0
    assert capsys.readouterr().out.strip() == "Explained in context."


def test_providers_check(setup, capsys):
    _, config, _ = setup
    assert main(["--config", config, "providers", "--check"]) == 0
    out = capsys.readouterr().out
    assert "fake" in out and "Explained in context." in out
    assert "claude-cli" in out and "[preset]" in out


def test_config_init(tmp_path, capsys):
    path = tmp_path / "c.toml"
    assert main(["--config", str(path), "config", "--init"]) == 0
    assert path.exists()
    assert main(["--config", str(path), "config"]) == 0
    assert "default_provider" in capsys.readouterr().out


def test_bad_provider_is_reported(setup, capsys):
    _, config, pdf = setup
    assert main(["--config", config, "glossary", pdf, "--provider", "nope"]) == 1
    assert "No provider named" in capsys.readouterr().err


def test_ask(setup, capsys):
    _, config, pdf = setup
    assert main(["--config", config, "ask", pdf, "Does it use DFT?"]) == 0
    assert capsys.readouterr().out.strip() == "Explained in context."
