from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
import pytest
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError

import ai_shell_agent.generator as generator_module
from ai_shell_agent.generator import (
    GeminiCommandGenerator,
    GenerationError,
    OpenAICommandGenerator,
    ProviderCommandGenerator,
)
from ai_shell_agent.models import CommandPlan


class RaisingAgent:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def run_sync(self, prompt: str) -> None:
        raise self.error


class RecordingAgent:
    def __init__(self, plan: CommandPlan) -> None:
        self.plan = plan
        self.prompt = ""

    def run_sync(self, prompt: str) -> SimpleNamespace:
        self.prompt = prompt
        return SimpleNamespace(output=self.plan)


def generator_with_agent(agent: object, provider_label: str = "Gemini") -> ProviderCommandGenerator:
    return ProviderCommandGenerator(cast(Any, agent), provider_label=provider_label)


@pytest.mark.parametrize(
    ("generator_class", "key_name"),
    [
        (GeminiCommandGenerator, "GEMINI_API_KEY"),
        (OpenAICommandGenerator, "OPENAI_API_KEY"),
    ],
)
def test_missing_api_key_fails_before_client_creation(
    generator_class: type[GeminiCommandGenerator] | type[OpenAICommandGenerator],
    key_name: str,
) -> None:
    with pytest.raises(GenerationError, match=key_name):
        generator_class("")


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "authentication failed"),
        (429, "rate limit exceeded"),
        (503, "temporarily unavailable"),
        (400, "HTTP 400"),
    ],
)
@pytest.mark.parametrize("provider_label", ["Gemini", "OpenAI"])
def test_http_errors_are_sanitized(
    status: int, message: str, provider_label: str, tmp_path: Path
) -> None:
    error = ModelHTTPError(status, "test-model", body={"secret": "must not leak"})
    generator = generator_with_agent(RaisingAgent(error), provider_label)

    with pytest.raises(GenerationError, match=message) as captured:
        generator.generate("list files", cwd=tmp_path, shell="/bin/sh")

    assert provider_label in str(captured.value)
    assert "must not leak" not in str(captured.value)


def test_timeout_is_mapped(tmp_path: Path) -> None:
    request = httpx.Request("GET", "https://example.invalid")
    generator = generator_with_agent(RaisingAgent(httpx.ReadTimeout("late", request=request)))

    with pytest.raises(GenerationError, match="Gemini request timed out"):
        generator.generate("list files", cwd=tmp_path, shell="/bin/sh")


def test_agent_run_error_is_mapped(tmp_path: Path) -> None:
    generator = generator_with_agent(
        RaisingAgent(AgentRunError("invalid output")), provider_label="OpenAI"
    )

    with pytest.raises(GenerationError, match="OpenAI could not produce a valid command plan"):
        generator.generate("list files", cwd=tmp_path, shell="/bin/sh")


def test_prompt_contains_environment_without_full_cwd(tmp_path: Path) -> None:
    plan = CommandPlan(success=True, command="pwd", explanation="Show directory")
    agent = RecordingAgent(plan)
    generator = generator_with_agent(agent)

    assert generator.generate("where am I", cwd=tmp_path, shell="/bin/zsh") == plan
    assert "shell: zsh" in agent.prompt
    assert f"working directory name: {tmp_path.name}" in agent.prompt
    assert str(tmp_path) not in agent.prompt


def test_openai_generator_configures_timeout_and_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    client = object()
    provider = object()
    model = object()
    agent = object()

    def fake_client(**kwargs: object) -> object:
        calls["client"] = kwargs
        return client

    def fake_provider(*, openai_client: object) -> object:
        calls["provider_client"] = openai_client
        return provider

    def fake_model(model_name: str, *, provider: object) -> object:
        calls["model"] = (model_name, provider)
        return model

    def fake_agent(*, model: object, **kwargs: object) -> object:
        calls["agent"] = (model, kwargs)
        return agent

    monkeypatch.setattr(generator_module, "AsyncOpenAI", fake_client)
    monkeypatch.setattr(generator_module, "OpenAIProvider", fake_provider)
    monkeypatch.setattr(generator_module, "OpenAIModel", fake_model)
    monkeypatch.setattr(generator_module, "Agent", fake_agent)

    created = OpenAICommandGenerator("openai-test-key", model_name="gpt-test", timeout=12.5)

    assert calls["client"] == {
        "api_key": "openai-test-key",
        "timeout": 12.5,
        "max_retries": 2,
    }
    assert calls["provider_client"] is client
    assert calls["model"] == ("gpt-test", provider)
    assert calls["agent"][0] is model  # type: ignore[index]
    assert created._provider_label == "OpenAI"
