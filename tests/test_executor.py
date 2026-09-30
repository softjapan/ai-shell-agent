from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from ai_shell_agent.executor import ExecutionError, ExecutionTimeout, execute_command, resolve_shell


def test_execute_command_uses_validated_shell_and_returns_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(args: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_command("example-command", cwd=tmp_path, timeout=4.5, shell="/bin/sh")

    assert result.returncode == 7
    assert calls == [
        (
            [str(Path("/bin/sh").resolve()), "-c", "example-command"],
            {"cwd": tmp_path.resolve(), "check": False, "timeout": 4.5},
        )
    ]


def test_execute_command_maps_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="test", timeout=2)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(ExecutionTimeout, match="timed out after 2 seconds"):
        execute_command("sleep 9", cwd=tmp_path, timeout=2, shell="/bin/sh")


@pytest.mark.parametrize("shell", ["sh", "/bin/not-a-real-shell", "/usr/bin/python3"])
def test_resolve_shell_rejects_invalid_shell(shell: str) -> None:
    with pytest.raises(ExecutionError):
        resolve_shell(shell)


def test_execute_command_rejects_missing_cwd(tmp_path: Path) -> None:
    with pytest.raises(ExecutionError, match="working directory does not exist"):
        execute_command("pwd", cwd=tmp_path / "missing", timeout=2, shell="/bin/sh")
