import os

import pytest

from paratext.ai.prompts import DEFAULT_AUDIENCE
from paratext.ai.providers import CommandProvider, ProviderError
from paratext.config import Config, write_template


def test_missing_config_gives_offline_defaults(tmp_path):
    config = Config.load(tmp_path / "nope.toml")
    assert config.default_provider is None
    assert config.audience == DEFAULT_AUDIENCE
    assert config.make_provider() is None
    assert config.make_provider("none") is None


def test_template_round_trip(tmp_path):
    path = write_template(tmp_path / "sub" / "config.toml", audience="a high-school student")
    config = Config.load(path)
    assert config.default_provider == "claude-cli"
    assert config.audience == "a high-school student"
    assert isinstance(config.make_provider(), CommandProvider)
    assert config.make_provider("anthropic").model == "claude-opus-5-5"
    # the template leaves openai's model blank on purpose
    with pytest.raises(ProviderError, match="model"):
        config.make_provider("openai")
    with pytest.raises(FileExistsError):
        write_template(path)


def test_custom_provider_and_cache_dir(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text(
        'default_provider = "mine"\ncache_dir = "~/somewhere"\n\n'
        '[providers.mine]\nkind = "command"\ncommand = "my-llm --fast"\n'
    )
    config = Config.load(path)
    provider = config.make_provider()
    assert provider.command == ["my-llm", "--fast"]
    assert provider.name == "mine"
    assert config.cache_dir.name == "somewhere" and "~" not in str(config.cache_dir)
    assert config.provider_names()[0] == "mine"
    with pytest.raises(ProviderError, match="No provider named"):
        config.make_provider("other")


def test_save_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    config = Config(path=path)
    config.default_provider = "anthropic"
    config.audience = "a curious teenager"
    config.providers["anthropic"] = {"preset": "anthropic", "api_key": "sk-secret", "model": "claude-opus-5-5"}
    config.providers["mine"] = {"kind": "command", "command": ["my-llm"], "timeout": 60.0}
    saved = config.save()
    assert saved == path
    if os.name != "nt":
        assert oct(path.stat().st_mode & 0o777) == "0o600"
    again = Config.load(path)
    assert again.default_provider == "anthropic"
    assert again.audience == "a curious teenager"
    assert again.providers == config.providers
    assert again.make_provider().api_key == "sk-secret"
    assert again.make_provider("mine").timeout == 60.0


def test_web_permission_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    assert Config.load(path).allow_web is False
    config = Config(path=path, allow_web=True)
    config.save()
    assert "allow_web = true" in path.read_text() and Config.load(path).allow_web is True
    config.allow_web = False
    config.save()
    assert "allow_web" not in path.read_text() and Config.load(path).allow_web is False
