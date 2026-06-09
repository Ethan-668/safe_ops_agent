from __future__ import annotations

from pathlib import Path

from safety.rules import SENSITIVE_FILE_PATTERNS, SENSITIVE_PATHS, WRITE_WORDS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ROOT = PROJECT_ROOT / "sandbox"
ALLOWED_SANDBOX_REFERENCES = tuple(
    sorted(
        {
            "sandbox/tmp",
            "sandbox/logs",
            "sandbox/recycle_bin",
            "./sandbox/tmp",
            "./sandbox/logs",
            "./sandbox/recycle_bin",
            str((SANDBOX_ROOT / "tmp").resolve()).replace("\\", "/"),
            str((SANDBOX_ROOT / "logs").resolve()).replace("\\", "/"),
            str((SANDBOX_ROOT / "recycle_bin").resolve()).replace("\\", "/"),
        },
        key=len,
        reverse=True,
    )
)


def contains_sensitive_path(text: str) -> tuple[bool, str]:
    normalized = text.replace("\\", "/")
    for pattern in SENSITIVE_FILE_PATTERNS:
        if pattern.search(normalized):
            return True, f"命中敏感文件规则：{pattern.pattern}"

    masked = _mask_allowed_sandbox_references(normalized)
    for path in sorted(SENSITIVE_PATHS, key=len, reverse=True):
        if path == "/":
            if masked.strip() in {"/", "/*"}:
                return True, "命中系统根目录"
            continue
        if path in masked:
            return True, f"命中敏感路径：{path}"
    return False, ""


def is_write_request(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in WRITE_WORDS)


def is_under_directory(path: str | Path, root: str | Path) -> bool:
    try:
        resolved_path = Path(path).resolve()
        resolved_root = Path(root).resolve()
        resolved_path.relative_to(resolved_root)
        return True
    except (ValueError, RuntimeError):
        return False


def _mask_allowed_sandbox_references(text: str) -> str:
    masked = text
    for reference in ALLOWED_SANDBOX_REFERENCES:
        masked = masked.replace(reference, "<allowed_sandbox_path>")
    return masked
