from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_shell_agent.models import CommandPlan


def test_successful_plan_strips_command() -> None:
    plan = CommandPlan(success=True, command="  ls -la  ", explanation="List files")

    assert plan.command == "ls -la"
    assert plan.failure is None


@pytest.mark.parametrize(
    "values",
    [
        {"success": True, "command": None, "explanation": "x"},
        {"success": True, "command": "pwd", "explanation": "x", "failure": "bad"},
        {"success": False, "command": "pwd", "explanation": "x", "failure": "bad"},
        {"success": False, "command": None, "explanation": "x", "failure": None},
    ],
)
def test_plan_rejects_inconsistent_outcomes(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CommandPlan.model_validate(values)


@pytest.mark.parametrize("command", ["ls\npwd", "ls\rpwd", "printf '\0'"])
def test_plan_rejects_control_characters(command: str) -> None:
    with pytest.raises(ValidationError):
        CommandPlan(success=True, command=command, explanation="Unsafe shape")
