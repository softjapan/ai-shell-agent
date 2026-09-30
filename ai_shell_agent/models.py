"""Validated domain models used by the command generation pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class RiskLevel(str, Enum):
    """Locally assessed command risk."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class CommandPlan(BaseModel):
    """Structured, validated output returned by the language model."""

    success: bool
    command: str | None = Field(default=None, max_length=4_000)
    explanation: str = Field(min_length=1, max_length=1_000)
    failure: str | None = Field(default=None, max_length=1_000)

    @field_validator("command")
    @classmethod
    def validate_command(cls, command: str | None) -> str | None:
        """Reject command text that cannot be safely presented as one command line."""
        if command is None:
            return None
        command = command.strip()
        if not command:
            raise ValueError("command must not be empty")
        if any(character in command for character in ("\n", "\r", "\0")):
            raise ValueError("command must be a single line without NUL characters")
        return command

    @model_validator(mode="after")
    def validate_outcome(self) -> CommandPlan:
        """Require exactly one valid success or failure outcome."""
        if self.success:
            if self.command is None:
                raise ValueError("a successful plan requires a command")
            if self.failure is not None:
                raise ValueError("a successful plan cannot include a failure")
        else:
            if self.command is not None:
                raise ValueError("a failed plan cannot include a command")
            if self.failure is None or not self.failure.strip():
                raise ValueError("a failed plan requires a failure reason")
        return self


@dataclass(frozen=True)
class RiskAssessment:
    """Result of deterministic local command inspection."""

    level: RiskLevel
    reasons: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        """Return whether local policy forbids execution."""
        return self.level is RiskLevel.BLOCKED


@dataclass(frozen=True)
class ExecutionResult:
    """Shell process completion details."""

    returncode: int
