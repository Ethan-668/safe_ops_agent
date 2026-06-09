from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_int(value: Any, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        parsed = max(minimum, parsed)
    if maximum is not None:
        parsed = min(maximum, parsed)
    return parsed


def safe_path(value: Any, default: str = ".") -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    text = value.strip()
    if "\x00" in text:
        return default
    return text


def existing_path(value: Any, default: str = ".") -> str:
    path = Path(safe_path(value, default)).expanduser()
    if path.exists():
        return str(path)
    return default
