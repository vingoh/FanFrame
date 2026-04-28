import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if "openai" not in sys.modules:
    fake_openai = types.ModuleType("openai")
    fake_openai.OpenAI = object
    sys.modules["openai"] = fake_openai
if "dotenv" not in sys.modules:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = fake_dotenv
if "pydantic" not in sys.modules:
    fake_pydantic = types.ModuleType("pydantic")

    class _FakeBaseModel:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def _fake_field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    fake_pydantic.BaseModel = _FakeBaseModel
    fake_pydantic.Field = _fake_field
    sys.modules["pydantic"] = fake_pydantic
from core import llm as llm_module


@pytest.fixture
def clean_env(monkeypatch):
    for key in [
        "MODELSCOPE_API_KEY",
        "OPENAI_API_KEY",
        "ZHIPU_API_KEY",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL_ID",
        "LLM_TIMEOUT",
    ]:
        monkeypatch.delenv(key, raising=False)


def make_llm_without_init() -> llm_module.BaseLLM:
    return llm_module.BaseLLM.__new__(llm_module.BaseLLM)


def test_auto_detect_provider_by_env_priority(clean_env, monkeypatch):
    """测试 provider 在多种环境变量下的优先级判断。"""
    obj = make_llm_without_init()
    monkeypatch.setenv("MODELSCOPE_API_KEY", "ms-1")
    assert obj._auto_detect_provider(None, None) == "modelscope"

    monkeypatch.delenv("MODELSCOPE_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-1")
    assert obj._auto_detect_provider(None, None) == "openai"

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ZHIPU_API_KEY", "zp-1")
    assert obj._auto_detect_provider(None, None) == "zhipu"


@pytest.mark.parametrize(
    ("base_url", "expected"),
    [
        ("https://api-inference.modelscope.cn/v1", "modelscope"),
        ("https://open.bigmodel.cn/api/paas/v4", "zhipu"),
        ("http://localhost:11434/v1", "ollama"),
        ("http://127.0.0.1:8000/v1", "vllm"),
        ("http://127.0.0.1:9000/v1", "local"),
    ],
)
def test_auto_detect_provider_by_base_url(clean_env, base_url, expected):
    """测试 provider 能根据 base_url 映射到预期平台类型。"""
    obj = make_llm_without_init()
    assert obj._auto_detect_provider(None, base_url) == expected


def test_auto_detect_provider_by_api_key_prefix_or_default(clean_env):
    """测试 API Key 前缀识别与默认 auto 分支。"""
    obj = make_llm_without_init()
    assert obj._auto_detect_provider("ms-abc", None) == "modelscope"
    assert obj._auto_detect_provider(None, None) == "auto"


def test_resolve_credentials_for_openai(clean_env, monkeypatch):
    """测试 openai 分支的 key 与默认 base_url 解析。"""
    obj = make_llm_without_init()
    obj.provider = "openai"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    api_key, base_url = obj._resolve_credentials(None, None)
    assert api_key == "sk-openai"
    assert base_url == "https://api.openai.com/v1"


def test_resolve_credentials_for_modelscope(clean_env, monkeypatch):
    """测试 modelscope 分支的 key 与默认 base_url 解析。"""
    obj = make_llm_without_init()
    obj.provider = "modelscope"
    monkeypatch.setenv("MODELSCOPE_API_KEY", "ms-key")
    api_key, base_url = obj._resolve_credentials(None, None)
    assert api_key == "ms-key"
    assert base_url == "https://api-inference.modelscope.cn/v1"


def test_resolve_credentials_for_zhipu(clean_env, monkeypatch):
    """测试 zhipu 分支的 key 与默认 base_url 解析。"""
    obj = make_llm_without_init()
    obj.provider = "zhipu"
    monkeypatch.setenv("ZHIPU_API_KEY", "zp-key")
    api_key, base_url = obj._resolve_credentials(None, None)
    assert api_key == "zp-key"
    assert base_url == "https://open.bigmodel.cn/api/paas/v4"


def test_resolve_credentials_for_auto_branch(clean_env, monkeypatch):
    """测试 auto 分支从通用环境变量读取凭据与地址。"""
    obj = make_llm_without_init()
    obj.provider = "auto"
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")
    api_key, base_url = obj._resolve_credentials(None, None)
    assert api_key == "generic-key"
    assert base_url == "http://localhost:1234/v1"


def test_parse_non_stream_response_with_content_and_tool_calls():
    """测试非流式响应中 content/tool_calls/usage/raw 的解析。"""
    obj = make_llm_without_init()
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="hello",
                    tool_calls=[
                        SimpleNamespace(
                            id="call_1",
                            function=SimpleNamespace(name="Search", arguments='{"query":"nvidia"}'),
                        )
                    ],
                ),
                finish_reason="tool_calls",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        model_dump=lambda: {"ok": True},
    )
    parsed = obj._parse_non_stream_response(response)
    assert parsed.text == "hello"
    assert parsed.finish_reason == "tool_calls"
    assert parsed.tool_calls[0].name == "Search"
    assert parsed.tool_calls[0].args == '{"query":"nvidia"}'
    assert parsed.tool_calls[0].call_id == "call_1"
    assert parsed.usage.total_tokens == 3
    assert parsed.raw == {"ok": True}


def test_parse_non_stream_response_without_choices():
    """测试非流式响应在无 choices 时的兜底行为。"""
    obj = make_llm_without_init()
    response = SimpleNamespace(
        choices=[],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=0, total_tokens=4),
        model_dump=lambda: {"empty": True},
    )
    parsed = obj._parse_non_stream_response(response)
    assert parsed.text == ""
    assert parsed.tool_calls == []
    assert parsed.usage.total_tokens == 4
    assert parsed.raw == {"empty": True}


def test_parse_stream_response_merges_text_and_tool_calls():
    """测试流式分片的文本拼接与 tool_call 参数拼接。"""
    obj = make_llm_without_init()

    chunk1 = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=None,
                delta=SimpleNamespace(
                    content="你好，",
                    tool_calls=[],
                ),
            )
        ],
        usage=None,
    )
    chunk2 = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=None,
                delta=SimpleNamespace(
                    content="世界",
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id="call_abc",
                            function=SimpleNamespace(name="Search", arguments='{"query":"英伟'),
                        )
                    ],
                ),
            )
        ],
        usage=None,
    )
    chunk3 = SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason="stop",
                delta=SimpleNamespace(
                    content="",
                    tool_calls=[
                        SimpleNamespace(
                            index=0,
                            id=None,
                            function=SimpleNamespace(name="", arguments='达"}'),
                        )
                    ],
                ),
            )
        ],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    parsed = obj._parse_stream_response([chunk1, chunk2, chunk3])
    assert parsed.text == "你好，世界"
    assert parsed.finish_reason == "stop"
    assert parsed.usage.total_tokens == 15
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "Search"
    assert parsed.tool_calls[0].args == '{"query":"英伟达"}'
    assert parsed.tool_calls[0].call_id == "call_abc"


def test_think_passes_through_tools_and_tool_choice_stream(clean_env, monkeypatch):
    """测试 think 在流式模式下对 tools/tool_choice 的透传。"""
    monkeypatch.setenv("LLM_MODEL_ID", "demo-model")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")

    fake_create = MagicMock()
    fake_create.return_value = []

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
    )
    monkeypatch.setattr(llm_module, "OpenAI", lambda **kwargs: fake_client)

    client = llm_module.BaseLLM()
    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "Search"}}]
    client.think(messages, stream=True, tools=tools, tool_choice="auto")

    _, kwargs = fake_create.call_args
    assert kwargs["model"] == "demo-model"
    assert kwargs["messages"] == messages
    assert kwargs["stream"] is True
    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"


def test_think_non_stream_parses_response(clean_env, monkeypatch):
    """测试 think 在非流式模式下返回解析后的统一结构。"""
    monkeypatch.setenv("LLM_MODEL_ID", "demo-model")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1")

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="done", tool_calls=[]),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        model_dump=lambda: {"raw": 1},
    )
    fake_create = MagicMock(return_value=response)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fake_create)),
    )
    monkeypatch.setattr(llm_module, "OpenAI", lambda **kwargs: fake_client)

    client = llm_module.BaseLLM()
    parsed = client.think([{"role": "user", "content": "ok"}], stream=False)
    assert parsed.text == "done"
    assert parsed.finish_reason == "stop"
    assert parsed.usage.total_tokens == 2
