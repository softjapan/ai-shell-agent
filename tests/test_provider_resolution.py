from __future__ import annotations

import pytest

from ai_shell_agent.cli import resolve_provider
from ai_shell_agent.generator import DEFAULT_PROVIDER, PROVIDER_ENV_VAR, GenerationError


def test_defaults_to_google_without_configuration() -> None:
    assert resolve_provider(None, {}) == DEFAULT_PROVIDER


def test_environment_variable_sets_default() -> None:
    assert resolve_provider(None, {PROVIDER_ENV_VAR: "openai"}) == "openai"


def test_environment_variable_is_normalized() -> None:
    assert resolve_provider(None, {PROVIDER_ENV_VAR: "  OpenAI  "}) == "openai"


def test_cli_flag_overrides_environment_variable() -> None:
    assert resolve_provider("google", {PROVIDER_ENV_VAR: "openai"}) == "google"


def test_blank_environment_variable_falls_back_to_default() -> None:
    assert resolve_provider(None, {PROVIDER_ENV_VAR: "   "}) == DEFAULT_PROVIDER


def test_invalid_environment_variable_is_rejected() -> None:
    with pytest.raises(GenerationError, match=PROVIDER_ENV_VAR) as captured:
        resolve_provider(None, {PROVIDER_ENV_VAR: "anthropic"})

    assert "anthropic" not in str(captured.value)
