"""Provider-agnostic text completion backends.

Every backend implements ``Provider.complete(system, prompt, json_schema=None) -> str``.
Three kinds cover most ways a user can reach a model:

- ``OpenAICompatibleProvider``: any server speaking the OpenAI chat-completions
  protocol (OpenAI, Google Gemini's OpenAI endpoint, OpenRouter, Groq, Together,
  Mistral, local Ollama / LM Studio / vLLM, ...).  Uses only the stdlib.
- ``AnthropicProvider``: Claude via the official ``anthropic`` SDK (optional extra).
- ``CommandProvider``: shells out to a CLI that is already signed in with the
  user's *subscription* (e.g. Claude Code ``claude -p``, OpenAI ``codex exec``,
  Google ``gemini``), so no API key is needed.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import shutil
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """A provider could not produce a completion (bad config, network, refusal, ...)."""


class Provider:
    """Base class: a named text-completion backend."""

    #: human-readable identifier, also part of the cache key
    name: str = "provider"

    def complete(self, system: str, prompt: str, json_schema: dict | None = None, web: bool = False) -> str:
        """Return the model's text reply.

        :param system: system / instruction prompt
        :param prompt: user prompt
        :param json_schema: if given, the caller expects a JSON object matching
            this schema.  Backends that support constrained output use it;
            others rely on the prompt asking for JSON.
        :param web: let the model search the web and fetch pages for this request (the reader's
            permission); only providers with :attr:`supports_web` accept it.
        """
        raise NotImplementedError

    @property
    def supports_web(self) -> bool:
        """Whether ``complete(..., web=True)`` gives the model web search and page fetching."""
        return False

    def _check_web(self, web: bool) -> None:
        if web and not self.supports_web:
            raise ProviderError(f"{self.name}: web search is not available with this provider.")

    @property
    def cache_key(self) -> str:
        return self.name

    @property
    def summary(self) -> str:
        """Model and settings in words, for the main window ("claude-opus-5-5, effort low")."""
        return self.cache_key


def _resolve_api_key(api_key: str | None, api_key_env: str | None, required: bool) -> str | None:
    if api_key:
        return api_key
    if api_key_env:
        value = os.environ.get(api_key_env)
        if value:
            return value
        if required:
            raise ProviderError(f"Environment variable {api_key_env} is not set (it should hold your API key).")
    return None


@dataclass
class OpenAICompatibleProvider(Provider):
    base_url: str
    model: str
    api_key: str | None = None
    api_key_env: str | None = None
    #: send ``response_format={"type": "json_object"}`` when JSON is requested
    #: (supported by OpenAI, Ollama and others, but not every server)
    json_mode: bool = False
    #: sent as ``reasoning_effort`` when non-empty (OpenAI reasoning models only)
    effort: str = ""
    timeout: float = 120.0
    extra_headers: dict = field(default_factory=dict)
    name: str = "openai-compatible"

    def __post_init__(self):
        if not self.model:
            raise ProviderError(f"Provider {self.name!r} needs a 'model' setting.")

    @property
    def cache_key(self) -> str:
        return f"{self.name}:{self.model}" + (f":{self.effort}" if self.effort else "")

    @property
    def summary(self) -> str:
        return self.model + (f", effort {self.effort}" if self.effort else "")

    def complete(self, system: str, prompt: str, json_schema: dict | None = None, web: bool = False) -> str:
        self._check_web(web)
        key = _resolve_api_key(self.api_key, self.api_key_env, required=self.api_key_env is not None)
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        if json_schema is not None and self.json_mode:
            body["response_format"] = {"type": "json_object"}
        if self.effort:
            body["reasoning_effort"] = self.effort
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        url = self.base_url.rstrip("/") + "/chat/completions"
        request = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            raise ProviderError(f"{self.name}: HTTP {e.code} from {url}: {detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ProviderError(f"{self.name}: could not reach {url}: {e}") from e
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise ProviderError(f"{self.name}: unexpected response: {str(payload)[:500]}") from e
        if isinstance(content, list):  # some servers return content parts
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""


# Models that accept the server-side refusal fallback (``fallbacks: "default"``)
_FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


@dataclass
class AnthropicProvider(Provider):
    model: str = "claude-opus-5-5"
    #: ``output_config.effort``; "" omits it (for models without effort support)
    effort: str = "low"
    max_tokens: int = 16000
    api_key: str | None = None
    api_key_env: str | None = None
    #: re-run refused requests on Anthropic's recommended fallback model;
    #: None means "on for models that support it"
    refusal_fallback: bool | None = None
    timeout: float = 120.0
    #: per-request timeout when web search is on (the server runs several searches and fetches per request)
    web_timeout: float = 600.0
    #: cap on web searches per request
    web_max_searches: int = 5
    name: str = "anthropic"

    @property
    def cache_key(self) -> str:
        return f"{self.name}:{self.model}" + (f":{self.effort}" if self.effort else "")

    @property
    def summary(self) -> str:
        return f"{self.model}, effort {self.effort or 'default'}"

    @property
    def supports_web(self) -> bool:
        return True

    def _client(self, anthropic, timeout: float | None = None):
        key = _resolve_api_key(self.api_key, self.api_key_env, required=self.api_key_env is not None)
        timeout = timeout or self.timeout
        # With no explicit key the SDK resolves ANTHROPIC_API_KEY / an `ant auth login` profile itself.
        if key:
            return anthropic.Anthropic(api_key=key, timeout=timeout)
        return anthropic.Anthropic(timeout=timeout)

    def web_tools(self) -> list[dict]:
        """Server-side web search and fetch (run by Anthropic; nothing to execute here)."""
        return [
            {"type": "web_search_20260209", "name": "web_search", "max_uses": self.web_max_searches},
            {"type": "web_fetch_20260209", "name": "web_fetch"},
        ]

    def request_kwargs(self, system: str, prompt: str, json_schema: dict | None = None, web: bool = False) -> dict:
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        if web:
            kwargs["tools"] = self.web_tools()
        output_config = {}
        if self.effort:
            output_config["effort"] = self.effort
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}
        if output_config:
            kwargs["output_config"] = output_config
        fallback = self.refusal_fallback if self.refusal_fallback is not None else self.model in _FALLBACK_MODELS
        if fallback:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
        return kwargs

    #: how many times a web request paused by the server-side tool loop is resumed
    MAX_CONTINUATIONS = 5

    def complete(self, system: str, prompt: str, json_schema: dict | None = None, web: bool = False) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise ProviderError("The Anthropic provider needs the SDK: pip install 'paratext[anthropic]'") from e
        client = self._client(anthropic, self.web_timeout if web else None)
        kwargs = self.request_kwargs(system, prompt, json_schema, web)
        texts = []
        for _ in range(self.MAX_CONTINUATIONS + 1):
            try:
                response = client.beta.messages.create(**kwargs)
            except anthropic.AuthenticationError as e:
                raise ProviderError("anthropic: authentication failed; check ANTHROPIC_API_KEY.") from e
            except anthropic.APIError as e:
                raise ProviderError(f"anthropic: {e}") from e
            if response.stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                category = getattr(details, "category", None) if details else None
                raise ProviderError(f"anthropic: the model declined this request (category: {category}).")
            texts.append("".join(block.text for block in response.content if block.type == "text"))
            if response.stop_reason != "pause_turn":
                break
            # the server-side search loop hit its iteration limit: send the turn back and it carries on
            kwargs["messages"] = [kwargs["messages"][0], {"role": "assistant", "content": response.content}]
        return "".join(texts)


@dataclass
class CommandProvider(Provider):
    """Run a local command; the prompt goes to stdin (or as the last argument)."""

    command: list[str] | str = field(default_factory=list)
    prompt_via: str = "stdin"  # or "arg"
    #: model name, inserted into ``model_args`` (e.g. ``["--model", "{model}"]``) when non-empty
    model: str = ""
    model_args: list[str] = field(default_factory=list)
    #: effort level, inserted into ``effort_args`` (e.g. ``["--effort", "{effort}"]``) when non-empty
    effort: str = ""
    effort_args: list[str] = field(default_factory=list)
    #: added when the reader allows web search, e.g. Claude Code's ``--tools WebSearch,WebFetch --allowedTools …``
    web_args: list[str] = field(default_factory=list)
    timeout: float = 300.0
    #: timeout when web search is on (searching and reading cited papers takes a while)
    web_timeout: float = 900.0
    name: str = "command"

    def __post_init__(self):
        if isinstance(self.command, str):
            self.command = shlex.split(self.command)
        if not self.command:
            raise ProviderError(f"Provider {self.name!r} needs a 'command' setting.")
        if self.prompt_via not in ("stdin", "arg"):
            raise ProviderError("prompt_via must be 'stdin' or 'arg'")
        if self.model and not self.model_args:
            raise ProviderError(f"Provider {self.name!r} has a model but no 'model_args' to pass it with.")
        if self.effort and not self.effort_args:
            raise ProviderError(f"Provider {self.name!r} has an effort but no 'effort_args' to pass it with.")

    @property
    def cache_key(self) -> str:
        return f"{self.name}:{' '.join(self.full_command())}"

    @property
    def summary(self) -> str:
        parts = [f"model {self.model}" if self.model else "default model"]
        if self.effort_args:
            parts.append(f"effort {self.effort or 'default'}")
        return f"{self.command[0]}: " + ", ".join(parts)

    @property
    def supports_web(self) -> bool:
        return bool(self.web_args)

    def full_command(self) -> list[str]:
        """The command with the model flag filled in."""
        args = list(self.command)
        if self.model:
            args += [a.format(model=self.model) for a in self.model_args]
        if self.effort:
            args += [a.format(effort=self.effort) for a in self.effort_args]
        return args

    def complete(self, system: str, prompt: str, json_schema: dict | None = None, web: bool = False) -> str:
        self._check_web(web)
        full_prompt = f"{system}\n\n{prompt}"
        args = self.full_command() + (list(self.web_args) if web else [])
        args += [full_prompt] if self.prompt_via == "arg" else []
        timeout = self.web_timeout if web else self.timeout
        try:
            result = subprocess.run(
                args,
                input=full_prompt if self.prompt_via == "stdin" else None,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as e:
            raise ProviderError(f"{self.name}: command not found: {self.command[0]}") from e
        except subprocess.TimeoutExpired as e:
            raise ProviderError(f"{self.name}: timed out after {timeout:.0f}s") from e
        if result.returncode != 0:
            raise ProviderError(f"{self.name}: exited with {result.returncode}: {result.stderr.strip()[:500]}")
        return result.stdout


# --------------------------------------------------------------------------
# Presets: named starting points; any field can be overridden in config.
# --------------------------------------------------------------------------

PRESETS: dict[str, dict] = {
    # API-key providers (pay-per-use developer accounts)
    "anthropic": {"kind": "anthropic", "model": "claude-opus-5-5"},
    "openai": {"kind": "openai", "base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
    "gemini": {
        "kind": "openai",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "api_key_env": "GEMINI_API_KEY",
    },
    "openrouter": {"kind": "openai", "base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"},
    # Local models (free, private)
    "ollama": {"kind": "openai", "base_url": "http://localhost:11434/v1", "json_mode": True},
    "lmstudio": {"kind": "openai", "base_url": "http://localhost:1234/v1"},
    # Subscription CLIs (sign in once with the vendor's own tool)
    "claude-cli": {
        "kind": "command",
        "command": ["claude", "-p"],
        "model_args": ["--model", "{model}"],
        "effort_args": ["--effort", "{effort}"],
        # only web search and page fetching, pre-approved: `-p` denies tools that would ask (checked 2026-11-05)
        "web_args": ["--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch"],
    },
    "codex-cli": {"kind": "command", "command": ["codex", "exec", "-"], "model_args": ["-m", "{model}"]},
    "gemini-cli": {"kind": "command", "command": ["gemini"], "model_args": ["-m", "{model}"]},
}

_KINDS = {"openai": OpenAICompatibleProvider, "anthropic": AnthropicProvider, "command": CommandProvider}


def make_provider(name: str, settings: dict | None = None) -> Provider:
    """Build a provider from a preset name and/or explicit settings.

    ``settings`` may contain ``preset`` (a key of ``PRESETS``), ``kind``
    ('openai', 'anthropic' or 'command') and any field of that provider class.
    If ``settings`` is None, ``name`` itself must be a preset.
    """
    settings = dict(settings or {})
    preset_name = settings.pop("preset", None) or (name if name in PRESETS else None)
    merged = dict(PRESETS.get(preset_name, {})) if preset_name else {}
    if preset_name and preset_name not in PRESETS:
        raise ProviderError(f"Unknown preset {preset_name!r}; choose from {', '.join(PRESETS)}")
    merged.update(settings)
    kind = merged.pop("kind", None)
    if kind is None:
        raise ProviderError(
            f"Provider {name!r} is not a preset and has no 'kind'. Presets: {', '.join(PRESETS)}; "
            "kinds: openai, anthropic, command."
        )
    if kind not in _KINDS:
        raise ProviderError(f"Unknown provider kind {kind!r}; use openai, anthropic or command.")
    cls = _KINDS[kind]
    allowed = set(cls.__dataclass_fields__)
    unknown = set(merged) - allowed
    if unknown:
        raise ProviderError(f"Unknown setting(s) for {kind} provider {name!r}: {', '.join(sorted(unknown))}")
    merged.setdefault("name", name)
    if kind == "openai":
        merged.setdefault("model", "")
    return cls(**merged)


# --------------------------------------------------------------------------
# Descriptions and readiness checks, for the setup dialog and `paratext providers`
# --------------------------------------------------------------------------


#: Claude Code accepts an alias for the latest model of a family, or a full model id to pin a version.
CLAUDE_CLI_ALIASES = ("fable", "opus", "sonnet", "haiku")
CLAUDE_CLI_MODELS = (
    *CLAUDE_CLI_ALIASES,
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
)


@dataclass(frozen=True)
class PresetInfo:
    title: str
    group: str  # "subscription", "api-key" or "local"
    description: str
    suggested_models: tuple[str, ...] = ()


PRESET_INFO: dict[str, PresetInfo] = {
    "claude-cli": PresetInfo(
        "Claude (Claude Code subscription)",
        "subscription",
        "Uses the Claude Code command-line tool, signed in with your Claude subscription. "
        "Install it from https://claude.com/claude-code, then run `claude` once in a terminal to sign in. "
        "'Check models' asks the tool which model each alias currently resolves to.",
        CLAUDE_CLI_MODELS,
    ),
    "codex-cli": PresetInfo(
        "ChatGPT (Codex CLI subscription)",
        "subscription",
        "Uses OpenAI's Codex command-line tool, signed in with your ChatGPT subscription. "
        "Install it (npm install -g @openai/codex), then run `codex` once to sign in.",
    ),
    "gemini-cli": PresetInfo(
        "Gemini (Gemini CLI)",
        "subscription",
        "Uses Google's Gemini command-line tool, signed in with your Google account. "
        "Install it (npm install -g @google/gemini-cli), then run `gemini` once to sign in.",
    ),
    "anthropic": PresetInfo(
        "Anthropic API key",
        "api-key",
        "Pay-per-use access to Claude with an API key from https://console.anthropic.com. "
        "Needs the SDK: pip install 'paratext[anthropic]'.",
        ("claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5", "claude-haiku-5-5"),
    ),
    "openai": PresetInfo(
        "OpenAI API key",
        "api-key",
        "Pay-per-use access with an API key from https://platform.openai.com. "
        "Press 'Fetch models' to list the chat models your key can use.",
    ),
    "gemini": PresetInfo(
        "Google Gemini API key",
        "api-key",
        "Pay-per-use access with an API key from https://aistudio.google.com. "
        "Press 'Fetch models' to list available models.",
    ),
    "openrouter": PresetInfo(
        "OpenRouter API key",
        "api-key",
        "One API key for models from many vendors (https://openrouter.ai). Press 'Fetch models' to list them.",
    ),
    "ollama": PresetInfo(
        "Ollama (local)",
        "local",
        "A model running on this computer with Ollama (https://ollama.com): free and private. "
        "Run `ollama pull <model>` first, then press 'Fetch models'.",
    ),
    "lmstudio": PresetInfo(
        "LM Studio (local)",
        "local",
        "A model served locally by LM Studio (https://lmstudio.ai). Start its server, then press 'Fetch models'.",
    ),
}

GROUP_TITLES = {
    "subscription": "Use a chat subscription (no API key)",
    "api-key": "Use an API key (pay per use)",
    "local": "Use a local model (free, private)",
}


EFFORT_LEVELS = {
    "anthropic": ("low", "medium", "high", "xhigh", "max"),
    "openai": ("", "low", "medium", "high"),
    "command": ("", "low", "medium", "high", "xhigh", "max"),
}


def provider_capabilities(settings: dict) -> dict:
    """Which settings a provider (merged preset + overrides) supports.

    Drives the setup dialog so each provider shows only what applies to it.
    Keys: ``api_key``, ``base_url``, ``model``, ``fetch_models``, ``command``
    (bools), ``effort`` (tuple of levels, or None), ``model_help``, ``effort_help``.
    """
    kind = settings.get("kind")
    caps = {
        "api_key": False,
        "base_url": False,
        "model": False,
        "fetch_models": False,
        "command": False,
        "effort": None,
        "model_help": "",
        "effort_help": "",
    }
    if kind == "anthropic":
        caps.update(
            api_key=True,
            model=True,
            effort=EFFORT_LEVELS["anthropic"],
            model_help="Opus is the most capable; Sonnet and Haiku are cheaper and faster.",
            effort_help="How much the model thinks before answering. Finding and explaining terms works well at "
            "'low'; raise it for dense papers. Higher levels cost more and take longer.",
        )
    elif kind == "openai":
        caps.update(
            api_key=bool(settings.get("api_key_env")),
            base_url=True,
            model=True,
            fetch_models=True,
            effort=EFFORT_LEVELS["openai"],
            model_help="'Fetch models' lists what this server offers; type a name if it is not listed.",
            effort_help="Sent as 'reasoning_effort'. Only reasoning models accept it; leave blank for other "
            "models and for local servers, which may reject it.",
        )
    elif kind == "command":
        is_claude = (settings.get("command") or [""])[0] == "claude"
        caps.update(
            command=True,
            model=bool(settings.get("model_args")),
            fetch_models=is_claude and bool(settings.get("model_args")),
            effort=EFFORT_LEVELS["command"] if settings.get("effort_args") else None,
            model_help=(
                "An alias ('fable', 'opus', 'sonnet', 'haiku') means the latest model of that family; a full id "
                "such as claude-opus-5-5 pins a version. Leave blank for the tool's default. "
                "'Check models' runs a one-word prompt per alias to see what it resolves to and which you can use."
                if is_claude
                else "Leave blank for the tool's default. Passed as its model flag "
                f"({' '.join(settings.get('model_args', []))})."
            ),
            effort_help="Passed as the tool's effort flag "
            f"({' '.join(settings.get('effort_args', []))}). Blank keeps the tool's default. "
            "Finding and explaining terms works well at 'low'.",
        )
    return caps


def probe_claude_models(command: list[str] | str, timeout: float = 120.0) -> dict[str, str]:
    """Ask Claude Code which model each alias resolves to, by running a one-word prompt per alias.

    Returns ``{alias: model_id}`` for the aliases the signed-in account can use (others are left out).
    ``command`` is the configured command (``["claude", "-p"]`` plus any extra flags).
    """
    if isinstance(command, str):
        command = shlex.split(command)
    if not command or shutil.which(command[0]) is None:
        raise ProviderError(f"`{command[0] if command else 'claude'}` is not installed (or not on your PATH).")
    base = [a for a in command if a != "-p"]
    resolved: dict[str, str] = {}
    failures = []
    for alias in CLAUDE_CLI_ALIASES:
        args = [*base, "-p", "--model", alias, "--effort", "low", "--output-format", "json"]
        try:
            result = subprocess.run(
                args, input="Reply with the single word OK.", capture_output=True, text=True, timeout=timeout
            )
        except subprocess.TimeoutExpired:
            failures.append(f"{alias}: timed out")
            continue
        if result.returncode != 0:
            failures.append(f"{alias}: {result.stderr.strip()[:120] or 'exited with ' + str(result.returncode)}")
            continue
        try:
            usage = json.loads(result.stdout).get("modelUsage") or {}
        except (json.JSONDecodeError, AttributeError):
            failures.append(f"{alias}: unexpected output")
            continue
        # The run may also bill a small helper model; pick the id that names the alias's family.
        ids = [m for m in usage if alias in m] or [m for m in usage if "haiku" not in m] or list(usage)
        if ids:
            resolved[alias] = ids[0]
    if not resolved:
        raise ProviderError("No model alias worked: " + "; ".join(failures))
    return resolved


def preset_status(name: str, settings: dict | None = None) -> tuple[bool, str]:
    """Check whether a provider looks usable without calling it.

    Returns ``(ready, message)``; the message says what is missing.
    """
    merged = dict(PRESETS.get((settings or {}).get("preset") or name, {}))
    merged.update(settings or {})
    kind = merged.get("kind")
    if kind == "command":
        command = merged.get("command") or []
        if isinstance(command, str):
            command = shlex.split(command)
        if not command:
            return False, "No command set."
        if shutil.which(command[0]) is None:
            return False, f"`{command[0]}` is not installed (or not on your PATH)."
        return True, f"`{command[0]}` found."
    if kind == "anthropic":
        if importlib.util.find_spec("anthropic") is None:
            return False, "The Anthropic SDK is not installed: pip install 'paratext[anthropic]'"
        if merged.get("api_key") or os.environ.get(merged.get("api_key_env") or "ANTHROPIC_API_KEY"):
            return True, "API key found."
        return False, "No API key: set ANTHROPIC_API_KEY or enter one in the setup dialog."
    if kind == "openai":
        env = merged.get("api_key_env")
        if env and not (merged.get("api_key") or os.environ.get(env)):
            return False, f"No API key: set {env} or enter one in the setup dialog."
        if not merged.get("model"):
            return False, "No model chosen."
        return True, "Key and model set."
    return False, "Unknown provider kind."


def list_models(base_url: str, api_key: str | None = None, timeout: float = 15.0) -> list[str]:
    """List model ids from an OpenAI-compatible server's ``/models`` endpoint."""
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        raise ProviderError(f"HTTP {e.code} from {url}: {e.read().decode(errors='replace')[:300]}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise ProviderError(f"Could not reach {url}: {e}") from e
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")] if isinstance(items, list) else []
    return sorted(ids)
