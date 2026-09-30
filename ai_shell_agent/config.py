"""Optional ``.env`` support that never overrides real environment variables.

Environment variables always win. A ``.env`` file only fills in keys that are
absent from the process environment, so secrets managed by the shell, CI, or a
secrets manager take precedence and are never shadowed by an on-disk file.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

_QUOTE_PAIRS = (('"', '"'), ("'", "'"))


def parse_env_file(text: str) -> dict[str, str]:
    """Parse ``.env`` content into key/value pairs.

    Supports ``KEY=value``, ``export KEY=value``, blank lines, ``#`` comments,
    surrounding single or double quotes, and inline comments after unquoted
    values. Lines without a key or ``=`` are ignored.
    """
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, remainder = line.partition("=")
        if not separator:
            continue
        key = key.strip()
        if not key.isidentifier():
            continue
        values[key] = _parse_value(remainder.strip())
    return values


def _parse_value(value: str) -> str:
    for opening, closing in _QUOTE_PAIRS:
        if len(value) >= 2 and value.startswith(opening) and value.endswith(closing):
            return value[1:-1]
    comment_index = value.find(" #")
    if comment_index != -1:
        value = value[:comment_index].rstrip()
    return value


def load_environment(
    base_environ: Mapping[str, str] | None = None,
    *,
    env_file: Path | None = None,
) -> dict[str, str]:
    """Return an environment mapping, filling missing keys from ``env_file``.

    Existing keys in ``base_environ`` are preserved as-is; only keys that are
    absent are supplemented from the file. A missing file is ignored.
    """
    merged: dict[str, str] = dict(os.environ if base_environ is None else base_environ)
    if env_file is None:
        return merged
    try:
        text = env_file.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError):
        return merged
    for key, value in parse_env_file(text).items():
        merged.setdefault(key, value)
    return merged
