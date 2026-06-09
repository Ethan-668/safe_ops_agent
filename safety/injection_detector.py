from __future__ import annotations

from safety.rules import PROMPT_INJECTION_PATTERNS


def detect_prompt_injection(text: str) -> tuple[bool, str]:
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern.search(text):
            return True, f"命中提示词注入规则：{pattern.pattern}"
    return False, ""
