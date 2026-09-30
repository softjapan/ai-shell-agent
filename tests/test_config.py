from __future__ import annotations

from pathlib import Path

from ai_shell_agent.config import load_environment, parse_env_file


def test_parse_env_file_handles_common_forms() -> None:
    text = "\n".join(
        [
            "# comment line",
            "",
            "GEMINI_API_KEY=plain-value",
            "export OPENAI_API_KEY=exported-value",
            'QUOTED="double quoted"',
            "SINGLE='single quoted'",
            "WITH_COMMENT=value # trailing comment",
            "  SPACED = spaced-value ",
            "not-an-identifier=ignored",
            "NO_SEPARATOR",
        ]
    )

    parsed = parse_env_file(text)

    assert parsed == {
        "GEMINI_API_KEY": "plain-value",
        "OPENAI_API_KEY": "exported-value",
        "QUOTED": "double quoted",
        "SINGLE": "single quoted",
        "WITH_COMMENT": "value",
        "SPACED": "spaced-value",
    }


def test_environment_variables_take_precedence(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from-file\nOPENAI_API_KEY=from-file\n", encoding="utf-8")

    merged = load_environment({"GEMINI_API_KEY": "from-env"}, env_file=env_file)

    assert merged["GEMINI_API_KEY"] == "from-env"
    assert merged["OPENAI_API_KEY"] == "from-file"


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    merged = load_environment({"SHELL": "/bin/sh"}, env_file=tmp_path / "absent.env")

    assert merged == {"SHELL": "/bin/sh"}


def test_none_env_file_returns_base(tmp_path: Path) -> None:
    merged = load_environment({"SHELL": "/bin/sh"}, env_file=None)

    assert merged == {"SHELL": "/bin/sh"}
