"""LLM client abstraction tests (unit, no API keys)."""

from types import SimpleNamespace as NS

import pytest

from synthea_omop_fhir.agent.llm import create_llm_client, LLMResponse, ToolCall


def test_create_llm_client_rejects_unknown_provider():
    with pytest.raises(ValueError):
        create_llm_client(provider="unknown")


def test_llm_response_dataclass():
    r = LLMResponse(
        stop_reason="tool_use",
        text="hello",
        tool_calls=[ToolCall(id="1", name="test", arguments={"a": 1})],
    )
    assert r.stop_reason == "tool_use"
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].arguments == {"a": 1}


def test_anthropic_adapter_with_fake():
    """Ensure _AnthropicAdapter wraps raw clients correctly."""

    class FakeMessages:
        def create(self, **_):
            tu = NS(type="tool_use", name="total_patients", id="t1", input={})
            return NS(stop_reason="tool_use", content=[tu])

    class FakeClient:
        messages = FakeMessages()

    client = create_llm_client(client=FakeClient())
    resp = client.chat_with_tools(
        system="s", messages=[{"role": "user", "content": "?"}], tools=[], max_tokens=10
    )
    assert resp.stop_reason == "tool_use"
    assert resp.tool_calls[0].name == "total_patients"
