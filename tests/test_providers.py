import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from paratext.ai.providers import (
    PRESET_INFO,
    PRESETS,
    AnthropicProvider,
    CommandProvider,
    OpenAICompatibleProvider,
    ProviderError,
    list_models,
    make_provider,
    preset_status,
    provider_capabilities,
)

# --------------------------------------------------------------------------
# OpenAI-compatible: a real local HTTP server
# --------------------------------------------------------------------------


@pytest.fixture
def chat_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append({"path": self.path, "headers": dict(self.headers), "body": body})
            if body["model"] == "broken":
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b'{"error": "bad key"}')
                return
            reply = {"choices": [{"message": {"role": "assistant", "content": "hello from " + body["model"]}}]}
            data = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            data = json.dumps({"data": [{"id": "m-b"}, {"id": "m-a"}, {"object": "x"}]}).encode()
            received.append({"path": self.path, "headers": dict(self.headers)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{server.server_port}/v1", received=received)
    server.shutdown()


def test_openai_compatible_roundtrip(chat_server, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "sk-test")
    p = OpenAICompatibleProvider(base_url=chat_server.url, model="m1", api_key_env="TEST_KEY", json_mode=True)
    assert p.complete("sys", "hi", json_schema={"type": "object"}) == "hello from m1"
    req = chat_server.received[0]
    assert req["path"] == "/v1/chat/completions"
    assert req["headers"]["Authorization"] == "Bearer sk-test"
    assert req["body"]["messages"] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
    assert req["body"]["response_format"] == {"type": "json_object"}


def test_openai_compatible_reasoning_effort(chat_server):
    p = OpenAICompatibleProvider(base_url=chat_server.url, model="m3", effort="high")
    p.complete("sys", "hi")
    assert chat_server.received[0]["body"]["reasoning_effort"] == "high"
    assert p.cache_key == "openai-compatible:m3:high"
    plain = OpenAICompatibleProvider(base_url=chat_server.url, model="m3")
    plain.complete("sys", "hi")
    assert "reasoning_effort" not in chat_server.received[1]["body"]
    assert plain.cache_key == "openai-compatible:m3"


def test_openai_compatible_no_key_no_json_mode(chat_server):
    p = OpenAICompatibleProvider(base_url=chat_server.url, model="m2")
    assert p.complete("sys", "hi", json_schema={"type": "object"}) == "hello from m2"
    req = chat_server.received[0]
    assert "Authorization" not in req["headers"]
    assert "response_format" not in req["body"]


def test_openai_compatible_http_error(chat_server):
    p = OpenAICompatibleProvider(base_url=chat_server.url, model="broken")
    with pytest.raises(ProviderError, match="HTTP 401"):
        p.complete("sys", "hi")


def test_openai_compatible_missing_env_key(monkeypatch):
    monkeypatch.delenv("NOT_SET_KEY", raising=False)
    p = OpenAICompatibleProvider(base_url="http://127.0.0.1:9", model="m", api_key_env="NOT_SET_KEY")
    with pytest.raises(ProviderError, match="NOT_SET_KEY"):
        p.complete("sys", "hi")


def test_openai_compatible_unreachable():
    p = OpenAICompatibleProvider(base_url="http://127.0.0.1:9/v1", model="m", timeout=2)
    with pytest.raises(ProviderError, match="could not reach"):
        p.complete("sys", "hi")


def test_openai_compatible_requires_model():
    with pytest.raises(ProviderError, match="model"):
        OpenAICompatibleProvider(base_url="http://x", model="")


# --------------------------------------------------------------------------
# Anthropic: stub the SDK client
# --------------------------------------------------------------------------


class StubMessages:
    def __init__(self, response):
        self.response = response
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def stub_client(response):
    messages = StubMessages(response)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def text_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
    )


def test_anthropic_request_shape(monkeypatch):
    pytest.importorskip("anthropic")
    client, messages = stub_client(text_response('{"terms": []}'))
    p = AnthropicProvider()
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: client)
    assert p.complete("sys", "prompt", json_schema={"type": "object"}) == '{"terms": []}'
    kw = messages.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["system"] == "sys"
    assert kw["messages"] == [{"role": "user", "content": "prompt"}]
    assert kw["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": {"type": "object"}}}
    assert kw["fallbacks"] == "default"
    assert kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "temperature" not in kw


def test_anthropic_no_fallback_for_other_models(monkeypatch):
    pytest.importorskip("anthropic")
    client, messages = stub_client(text_response("ok"))
    p = AnthropicProvider(model="claude-haiku-5-5", effort="")
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: client)
    p.complete("sys", "prompt")
    assert "fallbacks" not in messages.kwargs and "betas" not in messages.kwargs
    assert "output_config" not in messages.kwargs


def test_anthropic_refusal_raises(monkeypatch):
    pytest.importorskip("anthropic")
    client, _ = stub_client(text_response("", stop_reason="refusal"))
    p = AnthropicProvider()
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: client)
    with pytest.raises(ProviderError, match="declined.*cyber"):
        p.complete("sys", "prompt")


# --------------------------------------------------------------------------
# Command providers: real subprocesses
# --------------------------------------------------------------------------

ECHO = [sys.executable, "-c", "import sys; data = sys.stdin.read(); print('got:' + data.splitlines()[-1])"]


def test_command_provider_stdin():
    p = CommandProvider(command=ECHO)
    assert p.complete("system line", "last line").strip() == "got:last line"


def test_command_provider_arg():
    p = CommandProvider(
        command=[sys.executable, "-c", "import sys; print(sys.argv[-1].splitlines()[0])"], prompt_via="arg"
    )
    assert p.complete("system line", "prompt").strip() == "system line"


def test_command_provider_model_flag():
    echo_args = [sys.executable, "-c", "import sys; print(' '.join(sys.argv[1:]))"]
    p = CommandProvider(command=echo_args, model="sonnet", model_args=["--model", "{model}"])
    assert p.complete("s", "p").strip() == "--model sonnet"
    assert p.full_command()[-2:] == ["--model", "sonnet"]
    assert p.cache_key.endswith("--model sonnet")
    assert CommandProvider(command=echo_args, model_args=["--model", "{model}"]).full_command() == echo_args
    with pytest.raises(ProviderError, match="model_args"):
        CommandProvider(command=echo_args, model="x")


def test_cli_presets_take_a_model():
    p = make_provider("claude-cli", {"preset": "claude-cli", "model": "sonnet"})
    assert p.full_command() == ["claude", "-p", "--model", "sonnet"]
    p = make_provider("claude-cli", {"preset": "claude-cli", "model": "fable", "effort": "low"})
    assert p.full_command() == ["claude", "-p", "--model", "fable", "--effort", "low"]
    assert p.cache_key.endswith("--model fable --effort low")
    with pytest.raises(ProviderError, match="effort_args"):
        CommandProvider(command=["x"], effort="low")
    assert make_provider("codex-cli", {"preset": "codex-cli", "model": "m"}).full_command()[-2:] == ["-m", "m"]


def test_provider_capabilities():
    anth = provider_capabilities(PRESETS["anthropic"])
    assert anth["api_key"] and anth["model"] and anth["effort"] == ("low", "medium", "high", "xhigh", "max")
    assert not anth["fetch_models"] and not anth["command"]
    ollama = provider_capabilities(PRESETS["ollama"])
    assert ollama["fetch_models"] and ollama["base_url"] and not ollama["api_key"]
    assert ollama["effort"][0] == ""  # blank = don't send reasoning_effort
    cli = provider_capabilities(PRESETS["claude-cli"])
    assert cli["command"] and cli["model"] and cli["fetch_models"] and "alias" in cli["model_help"]
    assert cli["effort"] == ("", "low", "medium", "high", "xhigh", "max") and "--effort" in cli["effort_help"]
    codex = provider_capabilities(PRESETS["codex-cli"])
    assert codex["model"] and not codex["fetch_models"] and codex["effort"] is None
    assert not provider_capabilities({"kind": "command", "command": ["x"]})["model"]


def test_command_provider_string_command():
    p = CommandProvider(command=f'"{sys.executable}" -c "print(42)"')
    assert p.complete("s", "p").strip() == "42"


def test_command_provider_failures():
    with pytest.raises(ProviderError, match="not found"):
        CommandProvider(command=["definitely-not-a-real-command-xyz"]).complete("s", "p")
    failing = CommandProvider(command=[sys.executable, "-c", "import sys; sys.exit('boom')"])
    with pytest.raises(ProviderError, match="boom"):
        failing.complete("s", "p")
    slow = CommandProvider(command=[sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.5)
    with pytest.raises(ProviderError, match="timed out"):
        slow.complete("s", "p")


# --------------------------------------------------------------------------
# make_provider / presets
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["anthropic", "claude-cli", "codex-cli", "gemini-cli"])
def test_presets_without_required_settings(name):
    assert make_provider(name).name == name


def test_openai_presets_need_a_model():
    with pytest.raises(ProviderError, match="model"):
        make_provider("openai")
    p = make_provider("work", {"preset": "openai", "model": "some-model"})
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.base_url == PRESETS["openai"]["base_url"] and p.api_key_env == "OPENAI_API_KEY"
    assert p.cache_key == "work:some-model"


def test_make_provider_custom_kind():
    p = make_provider("local", {"kind": "openai", "base_url": "http://localhost:8000/v1", "model": "x"})
    assert p.base_url == "http://localhost:8000/v1"


def test_make_provider_errors():
    with pytest.raises(ProviderError, match="not a preset"):
        make_provider("mystery", {})
    with pytest.raises(ProviderError, match="Unknown preset"):
        make_provider("x", {"preset": "nope"})
    with pytest.raises(ProviderError, match="Unknown setting"):
        make_provider("x", {"preset": "anthropic", "colour": "red"})


# --------------------------------------------------------------------------
# readiness checks and model listing
# --------------------------------------------------------------------------


def test_every_preset_has_info():
    assert set(PRESET_INFO) == set(PRESETS)


def test_preset_status_command(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    ready, msg = preset_status("claude-cli")
    assert not ready and "claude" in msg and "not installed" in msg
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/local/bin/" + cmd)
    assert preset_status("claude-cli")[0]
    assert not preset_status("x", {"kind": "command", "command": []})[0]


def test_preset_status_anthropic(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    ready, msg = preset_status("anthropic")
    assert not ready and "ANTHROPIC_API_KEY" in msg
    assert preset_status("anthropic", {"preset": "anthropic", "api_key": "sk"})[0]
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk")
    assert preset_status("anthropic")[0]


def test_preset_status_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert "OPENAI_API_KEY" in preset_status("openai")[1]
    assert "model" in preset_status("openai", {"preset": "openai", "api_key": "k"})[1]
    assert preset_status("openai", {"preset": "openai", "api_key": "k", "model": "m"})[0]
    # local servers need no key
    assert "model" in preset_status("ollama")[1]
    assert preset_status("ollama", {"preset": "ollama", "model": "llama"})[0]


def test_list_models(chat_server):
    assert list_models(chat_server.url, "sk-x") == ["m-a", "m-b"]
    req = chat_server.received[0]
    assert req["path"] == "/v1/models" and req["headers"]["Authorization"] == "Bearer sk-x"
    with pytest.raises(ProviderError, match="Could not reach"):
        list_models("http://127.0.0.1:9/v1", timeout=2)


def test_probe_claude_models(tmp_path, monkeypatch):
    """A fake `claude` that answers --output-format json like the real tool (2.1.x)."""
    fake = tmp_path / "claude"
    fake.write_text(
        "#!/bin/sh\n"
        'case "$*" in *haiku*) echo \'{"result":"OK","modelUsage":{"claude-haiku-5-5":{}}}\' ;;\n'
        '*fable*) echo "no access" >&2; exit 1 ;;\n'
        '*opus*) echo \'{"result":"OK","modelUsage":{"claude-haiku-5-5":{},"claude-opus-5-5":{}}}\' ;;\n'
        '*) echo \'{"result":"OK","modelUsage":{"claude-haiku-5-5":{},"claude-sonnet-5-5":{}}}\' ;;\n'
        "esac\n"
    )
    fake.chmod(0o755)
    from paratext.ai.providers import probe_claude_models

    assert probe_claude_models([str(fake), "-p"]) == {
        "opus": "claude-opus-5-5",
        "sonnet": "claude-sonnet-5-5",
        "haiku": "claude-haiku-5-5",
    }
    with pytest.raises(ProviderError, match="not installed"):
        probe_claude_models(["definitely-not-a-real-command-xyz", "-p"])


def test_provider_summaries():
    assert make_provider("claude-cli", {"preset": "claude-cli"}).summary == "claude: default model, effort default"
    assert make_provider("claude-cli", {"preset": "claude-cli", "model": "opus", "effort": "max"}).summary == (
        "claude: model opus, effort max"
    )
    assert make_provider("ollama", {"preset": "ollama", "model": "llama3"}).summary == "llama3"
    assert make_provider("openai", {"preset": "openai", "model": "o3", "effort": "high", "api_key": "k"}).summary == (
        "o3, effort high"
    )


# --------------------------------------------------------------------------
# Web search (the reader's permission): which providers can, and how they are asked
# --------------------------------------------------------------------------


def test_web_search_support_by_provider():
    claude = make_provider("claude-cli", {"preset": "claude-cli", "model": "opus"})
    assert claude.supports_web and AnthropicProvider().supports_web
    assert not make_provider("codex-cli").supports_web and not make_provider("gemini-cli").supports_web
    assert not make_provider("ollama", {"preset": "ollama", "model": "m"}).supports_web
    with pytest.raises(ProviderError, match="web search is not available"):
        make_provider("ollama", {"preset": "ollama", "model": "m"}).complete("s", "p", web=True)
    # the web flags are not part of the cache key: the engine keys web answers itself
    assert "WebSearch" not in claude.cache_key


def test_command_web_args_only_with_permission():
    show_args = [sys.executable, "-c", "import sys; sys.stdin.read(); print(' '.join(sys.argv[1:]))"]
    p = CommandProvider(command=show_args, web_args=["--tools", "WebSearch,WebFetch"], web_timeout=60)
    assert p.complete("s", "p").strip() == ""
    assert p.complete("s", "p", web=True).strip() == "--tools WebSearch,WebFetch"
    assert make_provider("claude-cli").web_args == [
        "--tools",
        "WebSearch,WebFetch",
        "--allowedTools",
        "WebSearch,WebFetch",
    ]


def test_anthropic_web_tools_and_pause_turn(monkeypatch):
    pytest.importorskip("anthropic")
    paused = SimpleNamespace(
        stop_reason="pause_turn",
        stop_details=None,
        content=[SimpleNamespace(type="text", text="Searching. "), SimpleNamespace(type="server_tool_use")],
    )
    responses = [paused, text_response("Per Smith 2020, yes.")]
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return responses[len(calls) - 1]

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    timeouts = []
    p = AnthropicProvider()
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: timeouts.append(timeout) or client)
    assert p.complete("sys", "question", web=True) == "Searching. Per Smith 2020, yes."
    assert timeouts == [p.web_timeout]
    assert [t["type"] for t in calls[0]["tools"]] == ["web_search_20260209", "web_fetch_20260209"]
    assert calls[0]["tools"][0]["max_uses"] == 5
    # the paused turn is sent back as it is, with no extra "continue" message
    assert calls[1]["messages"] == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": paused.content},
    ]
    # without permission: no tools
    client2, messages = stub_client(text_response("ok"))
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: client2)
    p.complete("sys", "question")
    assert "tools" not in messages.kwargs


def test_command_provider_sends_utf8_whatever_the_locale(tmp_path):
    # paper text is full of Greek letters and symbols; with the locale's encoding (cp1252 on Windows, Latin-1
    # elsewhere) the prompt could not be written and the job failed with UnicodeEncodeError, not ProviderError
    echo = tmp_path / "echo.py"
    echo.write_text("import sys\nsys.stdout.buffer.write(sys.stdin.buffer.read())\n")
    p = CommandProvider(command=[sys.executable, str(echo)])
    text = "Tafel slope 118 mV dec⁻¹ at η = 0.3 V on α-MnO₂ (ΔG‡)"
    assert p.complete("system", text).endswith(text)


def test_command_provider_reports_a_command_it_cannot_run(tmp_path):
    script = tmp_path / "not-executable"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o644)
    with pytest.raises(ProviderError):
        CommandProvider(command=[str(script)]).complete("s", "p")


def test_anthropic_resumes_a_turn_paused_twice(monkeypatch):
    # every paused part of the turn goes back: sending only the latest part lost the searches already run
    pytest.importorskip("anthropic")
    first = SimpleNamespace(
        stop_reason="pause_turn", stop_details=None, content=[SimpleNamespace(type="text", text="One. ")]
    )
    second = SimpleNamespace(
        stop_reason="pause_turn", stop_details=None, content=[SimpleNamespace(type="text", text="Two. ")]
    )
    responses = [first, second, text_response("Done.")]
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return responses[len(calls) - 1]

    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    p = AnthropicProvider()
    monkeypatch.setattr(p, "_client", lambda anthropic, timeout=None: client)
    assert p.complete("sys", "question", web=True) == "One. Two. Done."
    assert calls[2]["messages"] == [
        {"role": "user", "content": "question"},
        {"role": "assistant", "content": first.content + second.content},
    ]
