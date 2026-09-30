"""Deterministic local safety policy for generated shell commands.

This is a guardrail, not a sandbox. A command that passes inspection can still be
harmful, so execution always requires explicit user action.
"""

from __future__ import annotations

import re
import shlex
from pathlib import PurePath

from ai_shell_agent.models import RiskAssessment, RiskLevel

_PATTERN_FLAGS = re.IGNORECASE

_BLOCKED_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:curl|wget)\b.*\|\s*(?:sudo\s+)?(?:ba|z|fi|c|k)?sh\b", _PATTERN_FLAGS),
        "downloads and executes a remote script",
    ),
    (
        re.compile(r"(?:^|[;&|]\s*)sudo(?:\s|$)", _PATTERN_FLAGS),
        "requests elevated privileges with sudo",
    ),
    (
        re.compile(r"\b(?:mkfs(?:\.[a-z0-9]+)?|fdisk|parted)\b", _PATTERN_FLAGS),
        "can overwrite disk or filesystem structures",
    ),
    (
        re.compile(r"\bdiskutil\s+(?:erase|partition|apfs\s+delete)", _PATTERN_FLAGS),
        "can erase or repartition a disk",
    ),
    (
        re.compile(r"\bdd\b[^;&|]*(?:\bof=|\bif=/dev/(?:zero|random|urandom))", _PATTERN_FLAGS),
        "performs a raw device or destructive byte copy",
    ),
    (
        re.compile(r"\b(?:shutdown|reboot|halt|poweroff)\b", _PATTERN_FLAGS),
        "can stop or restart the system",
    ),
    (
        re.compile(r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", _PATTERN_FLAGS),
        "matches a shell fork bomb",
    ),
    (
        re.compile(
            r"\brm\b[^;&|]*(?:--no-preserve-root|\s/(?:\s|$)|\s~(?:/|\s|$))", _PATTERN_FLAGS
        ),
        "attempts a broad deletion from a protected path",
    ),
    (
        re.compile(r"\b(?:chmod|chown)\b[^;&|]*\s-R\b[^;&|]*\s/(?:\s|$)", _PATTERN_FLAGS),
        "recursively changes permissions or ownership from filesystem root",
    ),
)

_HIGH_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?:^|[;&|]\s*)(?:rm|unlink|rmdir)\b", _PATTERN_FLAGS),
        "deletes files or directories",
    ),
    (re.compile(r"\bfind\b[^;&|]*\s-delete\b", _PATTERN_FLAGS), "deletes files selected by find"),
    (
        re.compile(
            r"\bgit\s+(?:reset\s+--hard|clean\s+-[^\s]*f|push\s+[^;&|]*--force)", _PATTERN_FLAGS
        ),
        "can irreversibly discard or overwrite Git history or files",
    ),
    (re.compile(r"\b(?:kill|pkill|killall)\b", _PATTERN_FLAGS), "terminates running processes"),
    (re.compile(r"\b(?:chmod|chown|chgrp)\b", _PATTERN_FLAGS), "changes permissions or ownership"),
    (
        re.compile(r"\b(?:drop\s+(?:database|table)|truncate\s+table)\b", _PATTERN_FLAGS),
        "performs destructive database operations",
    ),
    (
        re.compile(
            r"\b(?:npm|pnpm|yarn|pipx?|uv|brew|apt(?:-get)?|dnf)\s+(?:remove|uninstall|purge)\b",
            _PATTERN_FLAGS,
        ),
        "removes installed software",
    ),
    (
        re.compile(
            r"(?:/etc/shadow|/etc/sudoers|\.ssh/|\.aws/credentials|(?:^|/)\.env(?:\s|$))",
            _PATTERN_FLAGS,
        ),
        "accesses a commonly sensitive credential or system file",
    ),
)

_MEDIUM_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?:^|[;&|]\s*)(?:curl|wget|ssh|scp|sftp|rsync|nc|netcat)\b", _PATTERN_FLAGS),
        "uses the network or a remote host",
    ),
    (
        re.compile(r"(?:^|[;&|]\s*)(?:cp|mv|mkdir|touch|install|tee|sed\s+-i)\b", _PATTERN_FLAGS),
        "can modify local files",
    ),
    (
        re.compile(
            r"\b(?:npm|pnpm|yarn|pipx?|uv|brew|apt(?:-get)?|dnf)\s+(?:add|install|sync|upgrade|update)\b",
            _PATTERN_FLAGS,
        ),
        "installs or updates software",
    ),
    (re.compile(r"(?:^|[^<])>{1,2}(?!>)"), "redirects output to a file"),
    (re.compile(r"\$\(|`"), "uses shell command substitution"),
    (re.compile(r"\b(?:eval|exec|source)\b", _PATTERN_FLAGS), "evaluates additional shell content"),
)

_READ_ONLY_COMMANDS = frozenset(
    {
        "basename",
        "cat",
        "date",
        "df",
        "dirname",
        "du",
        "echo",
        "file",
        "find",
        "grep",
        "head",
        "id",
        "ls",
        "man",
        "printf",
        "pwd",
        "stat",
        "tail",
        "uname",
        "wc",
        "which",
        "whoami",
    }
)
_READ_ONLY_GIT_SUBCOMMANDS = frozenset({"branch", "diff", "log", "show", "status", "tag"})
_SHELL_CONTROL = re.compile(r"(?:&&|\|\||[;|<>])")


def _matches(command: str, rules: tuple[tuple[re.Pattern[str], str], ...]) -> tuple[str, ...]:
    return tuple(reason for pattern, reason in rules if pattern.search(command))


def _first_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError as exc:
        raise ValueError(f"invalid shell quoting: {exc}") from exc


def assess_command(command: str) -> RiskAssessment:
    """Assess a single-line command using local, model-independent rules."""
    if not command.strip():
        return RiskAssessment(RiskLevel.BLOCKED, ("command is empty",))
    if any(character in command for character in ("\n", "\r", "\0")):
        return RiskAssessment(
            RiskLevel.BLOCKED,
            ("command contains a newline, carriage return, or NUL character",),
        )

    blocked_reasons = _matches(command, _BLOCKED_RULES)
    if blocked_reasons:
        return RiskAssessment(RiskLevel.BLOCKED, blocked_reasons)

    high_reasons = _matches(command, _HIGH_RULES)
    if high_reasons:
        return RiskAssessment(RiskLevel.HIGH, high_reasons)

    medium_reasons = list(_matches(command, _MEDIUM_RULES))
    try:
        tokens = _first_tokens(command)
    except ValueError as exc:
        return RiskAssessment(RiskLevel.BLOCKED, (str(exc),))

    if not tokens:
        return RiskAssessment(RiskLevel.BLOCKED, ("command is empty",))

    executable = PurePath(tokens[0]).name.lower()
    read_only = executable in _READ_ONLY_COMMANDS
    if executable == "git":
        read_only = len(tokens) > 1 and tokens[1].lower() in _READ_ONLY_GIT_SUBCOMMANDS

    if _SHELL_CONTROL.search(command):
        medium_reasons.append("combines commands or uses shell control operators")

    if medium_reasons:
        return RiskAssessment(RiskLevel.MEDIUM, tuple(dict.fromkeys(medium_reasons)))
    if read_only:
        return RiskAssessment(RiskLevel.LOW, ("matches a recognized read-only command",))
    return RiskAssessment(
        RiskLevel.MEDIUM,
        ("command is not in the recognized read-only allowlist",),
    )
