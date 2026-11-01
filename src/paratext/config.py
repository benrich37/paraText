"""User configuration (TOML) and default paths.

Config file: ``$PARATEXT_CONFIG`` or ``~/.config/paratext/config.toml``.
Cache dir:   ``$PARATEXT_CACHE_DIR`` or ``~/.cache/paratext``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib

from paratext.ai.prompts import DEFAULT_AUDIENCE
from paratext.ai.providers import PRESETS, Provider, ProviderError, make_provider

CONFIG_TEMPLATE = """\
# paraText configuration.  Pick one provider as the default; any [providers.*]
# entry can start from a preset and override its fields.
#
# Presets: anthropic, openai, gemini, openrouter, ollama, lmstudio,
#          claude-cli, codex-cli, gemini-cli
#
# Keys are read from environment variables (api_key_env) so they never need to
# live in this file.

default_provider = "claude-cli"

# Who the explanations are written for.
audience = "{audience}"

# --- Use a chat subscription through the vendor's own CLI (no API key) ---
[providers.claude-cli]
preset = "claude-cli"          # Claude Code: run `claude` once to sign in

[providers.codex-cli]
preset = "codex-cli"           # OpenAI Codex CLI: run `codex` once to sign in

[providers.gemini-cli]
preset = "gemini-cli"          # Google Gemini CLI: run `gemini` once to sign in

# --- Pay-per-use API keys ---
[providers.anthropic]
preset = "anthropic"           # reads ANTHROPIC_API_KEY; needs: pip install 'paratext[anthropic]'
model = "claude-opus-5-5"
effort = "low"

[providers.openai]
preset = "openai"              # reads OPENAI_API_KEY
model = ""                     # set to a chat model your account can use

[providers.gemini]
preset = "gemini"              # reads GEMINI_API_KEY
model = ""

[providers.openrouter]
preset = "openrouter"          # reads OPENROUTER_API_KEY; one key, many vendors
model = ""

# --- Local models (free, private) ---
[providers.ollama]
preset = "ollama"              # run `ollama serve` and `ollama pull <model>` first
model = ""
"""


def default_config_path() -> Path:
    return Path(os.environ.get("PARATEXT_CONFIG", Path.home() / ".config" / "paratext" / "config.toml"))


def default_cache_dir() -> Path:
    return Path(os.environ.get("PARATEXT_CACHE_DIR", Path.home() / ".cache" / "paratext"))


@dataclass
class Config:
    default_provider: str | None = None
    audience: str = DEFAULT_AUDIENCE
    providers: dict[str, dict] = field(default_factory=dict)
    cache_dir: Path = field(default_factory=default_cache_dir)
    path: Path | None = None

    @classmethod
    def load(cls, path=None) -> Config:
        """Load the config file; a missing file gives the defaults (no provider)."""
        path = Path(path) if path else default_config_path()
        if not path.exists():
            return cls(path=path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        cache_dir = data.get("cache_dir")
        return cls(
            default_provider=data.get("default_provider") or None,
            audience=data.get("audience") or DEFAULT_AUDIENCE,
            providers=dict(data.get("providers", {})),
            cache_dir=Path(cache_dir).expanduser() if cache_dir else default_cache_dir(),
            path=path,
        )

    def save(self, path=None) -> Path:
        """Write the config as TOML (comments are not preserved).

        The file is made private (0600) because it may hold API keys.
        """
        path = Path(path) if path else (self.path or default_config_path())
        data = {}
        if self.default_provider:
            data["default_provider"] = self.default_provider
        data["audience"] = self.audience
        if self.cache_dir != default_cache_dir():
            data["cache_dir"] = str(self.cache_dir)
        if self.providers:
            data["providers"] = {
                name: {k: v for k, v in s.items() if v is not None} for name, s in self.providers.items()
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(tomli_w.dumps(data))
        try:
            os.chmod(tmp, 0o600)
        except OSError:  # pragma: no cover - e.g. unusual filesystems
            pass
        os.replace(tmp, path)
        self.path = path
        return path

    def provider_names(self) -> list[str]:
        return list(dict.fromkeys(list(self.providers) + list(PRESETS)))

    def make_provider(self, name: str | None = None) -> Provider | None:
        """Build the named (or default) provider; None means no AI (offline mode)."""
        name = name or self.default_provider
        if not name or name == "none":
            return None
        if name in self.providers:
            return make_provider(name, self.providers[name])
        if name in PRESETS:
            return make_provider(name)
        raise ProviderError(f"No provider named {name!r}. Configured: {', '.join(self.providers) or 'none'}")


def write_template(path=None, audience: str = DEFAULT_AUDIENCE) -> Path:
    path = Path(path) if path else default_config_path()
    if path.exists():
        raise FileExistsError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CONFIG_TEMPLATE.format(audience=audience))
    return path
