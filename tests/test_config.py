import os
import subprocess
import sys
import textwrap

import pytest

from paratext.ai.prompts import DEFAULT_AUDIENCE
from paratext.ai.providers import CommandProvider, ProviderError
from paratext.config import Config, ConfigError, write_template


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
    config.dev_provider, config.dev_ponytail = "claude-cli", "lite"
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
    assert (again.dev_provider, again.dev_ponytail) == ("claude-cli", "lite")


def test_web_permission_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    assert Config.load(path).allow_web is False
    config = Config(path=path, allow_web=True)
    config.save()
    assert "allow_web = true" in path.read_text() and Config.load(path).allow_web is True
    config.allow_web = False
    config.save()
    assert "allow_web" not in path.read_text() and Config.load(path).allow_web is False


def test_invalid_toml_names_the_file(tmp_path):
    from paratext.config import ConfigError
    from paratext.profile import UserProfile

    bad = tmp_path / "config.toml"
    bad.write_text("audience = \n")
    with pytest.raises(ConfigError, match="config.toml is not valid TOML"):
        Config.load(bad)
    profile = tmp_path / "profile.toml"
    profile.write_text("known = [\n")
    with pytest.raises(ConfigError, match="profile.toml"):
        UserProfile.load(profile)


def test_settings_files_are_utf8_whatever_the_locale(tmp_path):
    # Files were written in the locale's encoding. On Windows the profile's "…" became a byte that is not UTF-8,
    # so the next start could not read the profile, and accented or CJK text could not be saved at all. Every text
    # write left to the locale raises here, on any platform.
    script = textwrap.dedent(
        """
        import sys
        from pathlib import Path
        from paratext.config import Config, write_template
        from paratext.links import Link, link_body
        from paratext.profile import UserProfile

        d, text = Path(sys.argv[1]), "Schrödinger, Å, 电催化"
        Config(audience=text, path=d / "config.toml").save()
        assert Config.load(d / "config.toml").audience == text
        UserProfile(background=text, path=d / "profile.toml").save()
        assert UserProfile.load(d / "profile.toml").background == text
        write_template(d / "template.toml", audience=text)
        assert Config.load(d / "template.toml").audience == text
        (d / "data.csv").write_bytes(text.encode("utf-8"))
        assert link_body(Link(str(d / "data.csv")), 1000) == text
        """
    )
    flags = ["-X", "warn_default_encoding", "-W", "error::EncodingWarning"]
    result = subprocess.run([sys.executable, *flags, "-c", script, str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_config_that_is_not_utf8_is_reported(tmp_path):
    # tomllib raises UnicodeDecodeError, not TOMLDecodeError, for such a file: the reader crashed on start
    path = tmp_path / "config.toml"
    path.write_bytes('audience = "Schrödinger"\n'.encode("latin-1"))
    with pytest.raises(ConfigError, match="config.toml is not valid TOML"):
        Config.load(path)


def test_saving_over_a_broken_file_keeps_it(tmp_path):
    # The reader starts without a broken config, and its "Set up AI…" button is right there: saving from the
    # dialog replaced the hand-edited file, and with it every other provider in it
    path = tmp_path / "config.toml"
    broken = 'default_provider = "mine\n[providers.mine]\nkind = "command"\ncommand = ["my-llm"]\n'
    path.write_text(broken, encoding="utf-8")
    Config(default_provider="claude-cli", path=path).save()
    assert Config.load(path).default_provider == "claude-cli"
    assert (tmp_path / "config.toml.broken").read_text(encoding="utf-8") == broken
    Config(default_provider="anthropic", path=path).save()  # a valid file is simply replaced
    assert Config.load(path).default_provider == "anthropic"
    assert (tmp_path / "config.toml.broken").read_text(encoding="utf-8") == broken
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml", "config.toml.broken"]


def test_provider_that_is_not_a_table_is_reported(tmp_path):
    # valid TOML, wrong shape: make_provider raised ValueError when a paper was opened, and the setup dialog failed
    path = tmp_path / "config.toml"
    path.write_text('default_provider = "claude-cli"\n[providers]\nclaude-cli = "claude -p"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match=r"\[providers.claude-cli\]"):
        Config.load(path)
