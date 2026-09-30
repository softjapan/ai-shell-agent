from __future__ import annotations

import io

import pytest

from ai_shell_agent.formatting import Palette, should_use_color
from ai_shell_agent.models import RiskLevel


class FakeStream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_no_color_flag_disables_color() -> None:
    assert should_use_color(stream=FakeStream(True), no_color_flag=True, env={}) is False


def test_no_color_env_disables_color() -> None:
    assert (
        should_use_color(stream=FakeStream(True), no_color_flag=False, env={"NO_COLOR": "1"})
        is False
    )


def test_non_tty_disables_color() -> None:
    assert should_use_color(stream=FakeStream(False), no_color_flag=False, env={}) is False


def test_none_stream_disables_color() -> None:
    assert should_use_color(stream=None, no_color_flag=False, env={}) is False


def test_tty_enables_color() -> None:
    assert should_use_color(stream=FakeStream(True), no_color_flag=False, env={}) is True


def test_real_stringio_is_not_tty() -> None:
    assert should_use_color(stream=io.StringIO(), no_color_flag=False, env={}) is False


def test_palette_disabled_returns_plain_text() -> None:
    palette = Palette(enabled=False)

    assert palette.style("hello", "red", "bold") == "hello"
    assert palette.risk(RiskLevel.HIGH) == "high"


def test_palette_enabled_wraps_with_ansi() -> None:
    palette = Palette(enabled=True)
    styled = palette.style("hello", "red")

    assert styled.startswith("\033[")
    assert styled.endswith("\033[0m")
    assert "hello" in styled


@pytest.mark.parametrize(
    "level",
    [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.BLOCKED],
)
def test_palette_risk_contains_label_when_enabled(level: RiskLevel) -> None:
    palette = Palette(enabled=True)
    rendered = palette.risk(level)

    assert level.value in rendered
    assert rendered.startswith("\033[")
