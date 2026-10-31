import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest

from paratext.ai.providers import (
    PRESETS,
    AnthropicProvider,
    CommandProvider,
    OpenAICompatibleProvider,
    ProviderError,
    make_provider,
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
    monkeypatch.setattr(p, "_client", lambda anthropic: client)
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
    monkeypatch.setattr(p, "_client", lambda anthropic: client)
    p.complete("sys", "prompt")
    assert "fallbacks" not in messages.kwargs and "betas" not in messages.kwargs
    assert "output_config" not in messages.kwargs


def test_anthropic_refusal_raises(monkeypatch):
    pytest.importorskip("anthropic")
    client, _ = stub_client(text_response("", stop_reason="refusal"))
    p = AnthropicProvider()
    monkeypatch.setattr(p, "_client", lambda anthropic: client)
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
