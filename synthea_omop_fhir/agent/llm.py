"""Provider-agnostic LLM client abstraction (Anthropic, OpenAI, local).

Usage:
    from .llm import create_llm_client
    client = create_llm_client()          # picks provider from settings.llm_provider
    client = create_llm_client("openai")  # force provider
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ..config import settings


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    stop_reason: str  # "tool_use" | "stop"
    text: str
    tool_calls: list[ToolCall]


class LLMClient:
    """Abstract LLM client with tool-calling support."""

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicClient(LLMClient):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        import anthropic

        key = api_key or settings.anthropic_api_key
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your .env.")
        self.model = model or settings.anthropic_model
        self._client = anthropic.Anthropic(api_key=key)

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        tool_calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input or {})
            for b in resp.content
            if b.type == "tool_use"
        ]
        stop = "tool_use" if resp.stop_reason == "tool_use" else "stop"
        return LLMResponse(stop_reason=stop, text=text, tool_calls=tool_calls)


class _AnthropicAdapter(LLMClient):
    """Wrap a raw Anthropic client (e.g. test mocks) for backward compat."""

    def __init__(self, raw_client: Any):
        self._raw = raw_client
        self.model = getattr(raw_client, "model", settings.anthropic_model)

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        resp = self._raw.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        tool_calls = [
            ToolCall(id=b.id, name=b.name, arguments=b.input or {})
            for b in resp.content
            if b.type == "tool_use"
        ]
        stop = "tool_use" if resp.stop_reason == "tool_use" else "stop"
        return LLMResponse(stop_reason=stop, text=text, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIClient(LLMClient):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "",
    ):
        try:
            import openai
        except ImportError as exc:
            raise RuntimeError(
                "openai package is not installed. Run: uv add openai"
            ) from exc
        key = api_key or settings.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is not set. Add it to your .env.")
        self.model = model or settings.openai_model
        kwargs: dict[str, Any] = {"api_key": key}
        bu = base_url or settings.llm_base_url
        if bu:
            kwargs["base_url"] = bu
        self._client = openai.OpenAI(**kwargs)

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert Anthropic-style tool schema to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def _convert_messages(self, system: str, messages: list[dict]) -> list[dict]:
        """Convert internal Anthropic-flavoured history to OpenAI chat format."""
        out: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            role = m["role"]
            content = m.get("content")
            if role == "user" and isinstance(content, list):
                # tool_result blocks -> OpenAI tool messages
                for part in content:
                    if part.get("type") == "tool_result":
                        out.append(
                            {
                                "role": "tool",
                                "tool_call_id": part["tool_use_id"],
                                "content": part["content"],
                            }
                        )
                    else:
                        out.append({"role": role, "content": str(part)})
            elif role == "assistant" and isinstance(content, list):
                text_parts: list[str] = []
                tool_calls: list[dict] = []
                for part in content:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "tool_use":
                        tool_calls.append(
                            {
                                "id": part["id"],
                                "type": "function",
                                "function": {
                                    "name": part["name"],
                                    "arguments": json.dumps(part.get("input", {})),
                                },
                            }
                        )
                msg: dict[str, Any] = {"role": "assistant"}
                txt = " ".join(text_parts).strip()
                msg["content"] = txt or None
                if tool_calls:
                    msg["tool_calls"] = tool_calls
                out.append(msg)
            else:
                out.append(m)
        return out

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        oai_tools = self._convert_tools(tools)
        oai_msgs = self._convert_messages(system, messages)
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=oai_msgs,
            tools=oai_tools,
            tool_choice="auto",
            max_tokens=max_tokens,
        )
        choice = resp.choices[0]
        msg = choice.message
        text = msg.content or ""
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
            )
            for tc in (msg.tool_calls or [])
        ]
        stop = "tool_use" if choice.finish_reason == "tool_calls" else "stop"
        return LLMResponse(stop_reason=stop, text=text, tool_calls=tool_calls)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_llm_client(
    provider: str | None = None,
    client: Any | None = None,
) -> LLMClient:
    """Instantiate the right LLM client.

    If *client* is supplied and looks like a raw Anthropic client (has
    ``.messages``), it is wrapped for backward compatibility.
    """
    if client is not None:
        if hasattr(client, "messages"):
            return _AnthropicAdapter(client)
        if isinstance(client, LLMClient):
            return client
        raise TypeError(f"Unsupported client type: {type(client)}")
    prov = (provider or settings.llm_provider).lower()
    if prov == "anthropic":
        return AnthropicClient()
    if prov in ("openai",):
        return OpenAIClient()
    raise ValueError(f"Unsupported LLM provider: {prov}")
