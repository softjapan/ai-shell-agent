"""Minimal ANSI color helpers with no third-party dependencies.

Color is opt-in and safe for pipes and CI: it is only emitted when explicitly
enabled. Callers decide enablement from a TTY check, the ``NO_COLOR`` convention,
and a ``--no-color`` flag.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from ai_shell_agent.models import RiskLevel


class SupportsIsatty(Protocol):
    """Minimal stream protocol: only TTY detection is required."""

    def isatty(self) -> bool: ...


_RESET = "\033[0m"
_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "cyan": "36",
    "red_bg": "41;97",
}

_RISK_STYLES = {
    RiskLevel.LOW: ("green",),
    RiskLevel.MEDIUM: ("yellow",),
    RiskLevel.HIGH: ("red", "bold"),
    RiskLevel.BLOCKED: ("red_bg", "bold"),
}


def should_use_color(
    *,
    stream: SupportsIsatty | None,
    no_color_flag: bool,
    env: Mapping[str, str],
) -> bool:
    """Decide whether ANSI color should be emitted.

    Disabled when ``--no-color`` is set, when ``NO_COLOR`` is present (per the
    https://no-color.org convention), or when the stream is not a TTY.
    """
    if no_color_flag:
        return False
    if "NO_COLOR" in env:
        return False
    if stream is None:
        return False
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


@dataclass(frozen=True)
class Palette:
    """Applies ANSI styles when enabled; otherwise returns text unchanged."""

    enabled: bool

    def style(self, text: str, *styles: str) -> str:
        """Wrap text in the given named styles when color is enabled."""
        if not self.enabled or not styles:
            return text
        codes = ";".join(_CODES[name] for name in styles if name in _CODES)
        if not codes:
            return text
        return f"\033[{codes}m{text}{_RESET}"

    def risk(self, level: RiskLevel) -> str:
        """Render a risk level label with its severity color."""
        return self.style(level.value, *_RISK_STYLES.get(level, ()))
