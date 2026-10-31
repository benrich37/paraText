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
