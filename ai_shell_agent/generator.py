"""Provider-backed command generation isolated from execution concerns."""

from __future__ import annotations

import platform
from pathlib import Path, PurePath
from typing import Protocol

import httpx
from google.genai import Client
from google.genai.types import HttpOptions
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)
from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from ai_shell_agent.models import CommandPlan

DEFAULT_PROVIDER = "google"
PROVIDER_ENV_VAR = "AI_SHELL_AGENT_PROVIDER"
SUPPORTED_PROVIDERS = ("google", "openai")
DEFAULT_MODELS = {
    "google": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}
API_KEY_ENV_VARS = {
    "google": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}

SYSTEM_PROMPT = """\
You generate one shell command for the user's request.
Return a CommandPlan using the same language as the user for explanation and failure.
Do not reveal private chain-of-thought. Give only a concise explanation of what the command does
and its important side effects.

Rules:
- Return exactly one single-line command when success is true.
- Never include Markdown fences in the command.
- Prefer portable, least-privilege, non-destructive commands.
- Never add sudo unless the user explicitly requests elevated privileges.
- If the request is ambiguous or cannot be completed safely, return success=false with a
  clear reason.
- Do not claim that a command is safe; an independent local policy makes that decision.
"""


class GenerationError(RuntimeError):
    """Raised when a command plan cannot be generated."""


class CommandGenerator(Protocol):
    """Interface implemented by command generation backends."""

    def generate(self, request: str, *, cwd: Path, shell: str) -> CommandPlan:
        """Generate a structured command plan."""
        ...


class ProviderCommandGenerator:
    """Shared validated generation and sanitized provider error handling."""

    def __init__(self, agent: Agent[None, CommandPlan], *, provider_label: str) -> None:
        self._agent = agent
        self._provider_label = provider_label

    def generate(self, request: str, *, cwd: Path, shell: str) -> CommandPlan:
        """Generate a plan while converting provider failures to stable CLI errors."""
        environment = (
            f"Operating system: {platform.system()}; "
            f"shell: {PurePath(shell).name}; "
            f"working directory name: {cwd.name or '/'}"
        )
        prompt = f"{environment}\nUser request: {request}"
        try:
            return self._agent.run_sync(prompt).output
        except ModelHTTPError as exc:
            if exc.status_code in {401, 403}:
                detail = f"{self._provider_label} authentication failed"
            elif exc.status_code == 429:
                detail = f"{self._provider_label} rate limit exceeded; try again later"
            elif exc.status_code >= 500:
                detail = f"{self._provider_label} service is temporarily unavailable"
            else:
                detail = f"{self._provider_label} request failed with HTTP {exc.status_code}"
            raise GenerationError(detail) from exc
        except AuthenticationError as exc:
            raise GenerationError(f"{self._provider_label} authentication failed") from exc
        except RateLimitError as exc:
            raise GenerationError(
                f"{self._provider_label} rate limit exceeded; try again later"
            ) from exc
        except APITimeoutError as exc:
            raise GenerationError(f"{self._provider_label} request timed out") from exc
        except APIConnectionError as exc:
            raise GenerationError(f"{self._provider_label} connection failed") from exc
        except APIStatusError as exc:
            if exc.status_code >= 500:
                detail = f"{self._provider_label} service is temporarily unavailable"
            else:
                detail = f"{self._provider_label} request failed with HTTP {exc.status_code}"
            raise GenerationError(detail) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise GenerationError(f"{self._provider_label} request timed out") from exc
        except AgentRunError as exc:
            raise GenerationError(
                f"{self._provider_label} could not produce a valid command plan"
            ) from exc


class GeminiCommandGenerator(ProviderCommandGenerator):
    """Generate validated command plans with Google Gemini."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MODELS["google"],
        timeout: float = 30.0,
    ) -> None:
        _validate_configuration(api_key, timeout, API_KEY_ENV_VARS["google"])
        client = Client(
            api_key=api_key,
            http_options=HttpOptions(timeout=int(timeout * 1_000)),
        )
        model = GoogleModel(model_name, provider=GoogleProvider(client=client))
        agent: Agent[None, CommandPlan] = Agent(
            model=model,
            output_type=CommandPlan,
            system_prompt=SYSTEM_PROMPT,
            retries=2,
        )
        super().__init__(agent, provider_label="Gemini")


class OpenAICommandGenerator(ProviderCommandGenerator):
    """Generate validated command plans with the OpenAI API."""

    def __init__(
        self,
        api_key: str,
        *,
        model_name: str = DEFAULT_MODELS["openai"],
        timeout: float = 30.0,
    ) -> None:
        _validate_configuration(api_key, timeout, API_KEY_ENV_VARS["openai"])
        client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=2)
        model = OpenAIModel(
            model_name,
            provider=OpenAIProvider(openai_client=client),
        )
        agent: Agent[None, CommandPlan] = Agent(
            model=model,
            output_type=CommandPlan,
            system_prompt=SYSTEM_PROMPT,
            retries=2,
        )
        super().__init__(agent, provider_label="OpenAI")


def _validate_configuration(api_key: str, timeout: float, api_key_name: str) -> None:
    if not api_key.strip():
        raise GenerationError(f"{api_key_name} is not set")
    if timeout <= 0:
        raise GenerationError("API timeout must be greater than zero")


def create_generator(
    provider: str,
    api_key: str,
    *,
    model_name: str,
    timeout: float,
) -> CommandGenerator:
    """Create a command generator for a supported provider."""
    if provider == "google":
        return GeminiCommandGenerator(api_key, model_name=model_name, timeout=timeout)
    if provider == "openai":
        return OpenAICommandGenerator(api_key, model_name=model_name, timeout=timeout)
    raise GenerationError(f"unsupported provider: {provider}")
