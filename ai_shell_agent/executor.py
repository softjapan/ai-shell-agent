"""Controlled subprocess execution for approved shell commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ai_shell_agent.models import ExecutionResult

_ALLOWED_SHELL_NAMES = frozenset({"bash", "dash", "ksh", "sh", "zsh"})


class ExecutionError(RuntimeError):
    """Raised when a command cannot be started safely."""


class ExecutionTimeout(ExecutionError):
    """Raised when a command exceeds its execution deadline."""


def resolve_shell(shell: str | None = None) -> str:
    """Resolve and validate the shell executable used for command execution."""
    candidate = Path(shell or os.environ.get("SHELL", "/bin/sh")).expanduser()
    if not candidate.is_absolute():
        raise ExecutionError("shell path must be absolute")
    if candidate.name not in _ALLOWED_SHELL_NAMES:
        raise ExecutionError(f"unsupported shell: {candidate.name}")
    if not candidate.is_file() or not os.access(candidate, os.X_OK):
        raise ExecutionError(f"shell is not executable: {candidate}")
    return str(candidate.resolve())


def execute_command(
    command: str,
    *,
    cwd: Path,
    timeout: float,
    shell: str | None = None,
) -> ExecutionResult:
    """Execute an approved command and return its process exit status."""
    if timeout <= 0:
        raise ExecutionError("timeout must be greater than zero")
    resolved_cwd = cwd.expanduser().resolve()
    if not resolved_cwd.is_dir():
        raise ExecutionError(f"working directory does not exist: {resolved_cwd}")
    resolved_shell = resolve_shell(shell)

    try:
        completed = subprocess.run(
            [resolved_shell, "-c", command],
            cwd=resolved_cwd,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExecutionTimeout(f"command timed out after {timeout:g} seconds") from exc
    except OSError as exc:
        raise ExecutionError(f"could not start command: {exc}") from exc
    return ExecutionResult(returncode=completed.returncode)
