"""Bedrock backend tests with a mocked bedrock-runtime client (offline)."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from dhuan.agents.runtime import BedrockBackend
from dhuan.core.config import Settings

SETTINGS = Settings(env="test", bedrock_model_id="anthropic.claude-test", aws_region="ap-south-1")


class _FakeConverse:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self.response


def _install_fake_boto3(monkeypatch: pytest.MonkeyPatch, response: dict[str, Any]) -> _FakeConverse:
    fake = _FakeConverse(response)
    module = types.ModuleType("boto3")

    def client(_name: str, **_kwargs: Any) -> Any:
        return types.SimpleNamespace(converse=fake)

    module.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", module)
    return fake


TOOL_USE = {
    "output": {
        "message": {
            "content": [
                {"toolUse": {"name": "get_station_context", "input": {"lat": 28.6, "lon": 77.2}}}
            ]
        }
    }
}


async def test_bedrock_backend_returns_tool_call(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_boto3(monkeypatch, TOOL_USE)
    backend = BedrockBackend(SETTINGS)
    step = await backend.step(messages=[], tools=[{"name": "t"}], system="s", max_tokens=100)
    assert step.kind == "tool_call"
    assert step.tool_name == "get_station_context"
    assert step.tool_args["lat"] == 28.6
    call = fake.calls[0]
    assert call["modelId"] == "anthropic.claude-test"


async def test_bedrock_backend_returns_final_text(monkeypatch: pytest.MonkeyPatch) -> None:
    response = {"output": {"message": {"content": [{"text": "the answer"}]}}}
    _install_fake_boto3(monkeypatch, response)
    backend = BedrockBackend(SETTINGS)
    step = await backend.step(messages=[], tools=[], system="s", max_tokens=100)
    assert step.kind == "final"
    assert step.text == "the answer"


async def test_bedrock_backend_sends_tool_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _install_fake_boto3(monkeypatch, TOOL_USE)
    backend = BedrockBackend(SETTINGS)
    tools = [
        {
            "name": "find_upwind_sources",
            "description": "d",
            "parameters": {"type": "object", "properties": {}},
        }
    ]
    await backend.step(messages=[], tools=tools, system="s", max_tokens=100)
    config = fake.calls[0]["toolConfig"]
    assert config["tools"][0]["toolSpec"]["name"] == "find_upwind_sources"
