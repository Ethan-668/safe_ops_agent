from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

ERROR_CASE_FIELDS = [
    "id",
    "query",
    "expected_intent",
    "actual_intent",
    "expected_tools",
    "actual_tools",
    "expected_risk",
    "actual_risk",
    "source",
    "error_type",
    "brief_reason",
]

DEFAULT_EXPORTS = [
    (PROJECT_ROOT / "results" / "eval_results_llm.csv", PROJECT_ROOT / "results" / "error_cases_llm.csv"),
    (PROJECT_ROOT / "results" / "eval_results_fallback.csv", PROJECT_ROOT / "results" / "error_cases_fallback.csv"),
    (
        PROJECT_ROOT / "results" / "generalization_eval_results_llm.csv",
        PROJECT_ROOT / "results" / "generalization_error_cases_llm.csv",
    ),
    (
        PROJECT_ROOT / "results" / "generalization_eval_results_fallback.csv",
        PROJECT_ROOT / "results" / "generalization_error_cases_fallback.csv",
    ),
    (
        PROJECT_ROOT / "results" / "security_attack_results.csv",
        PROJECT_ROOT / "results" / "security_error_cases.csv",
    ),
]


def export_error_cases(rows: list[dict[str, Any]], path: str | Path) -> list[dict[str, str]]:
    """Export rows with intent, tool, or end-to-end task failures."""

    error_cases = [build_error_case(row) for row in rows if is_error_case(row)]
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=ERROR_CASE_FIELDS)
        writer.writeheader()
        writer.writerows(error_cases)
    return error_cases


def main() -> None:
    for input_path, output_path in DEFAULT_EXPORTS:
        if not input_path.exists():
            print(f"skip_missing: {input_path}")
            continue
        rows = load_rows(input_path)
        error_cases = export_error_cases(rows, output_path)
        print(f"{output_path}: {len(error_cases)}")


def load_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def is_error_case(row: dict[str, Any]) -> bool:
    return any(
        not _to_bool(row.get(field, "false"))
        for field in ("intent_correct", "tool_correct", "risk_correct", "task_success")
    )


def build_error_case(row: dict[str, Any]) -> dict[str, str]:
    error_types: list[str] = []
    reasons: list[str] = []
    source = str(row.get("source", "") or "unknown")
    source_label = "LLM" if source == "llm" else "fallback" if source == "fallback" else source

    if not _to_bool(row.get("intent_correct", "false")):
        error_types.append("intent_error")
        reasons.append(
            f"{source_label} 将意图识别为 {row.get('actual_intent', '') or '-'}，期望为 {row.get('expected_intent', '') or '-'}。"
        )
    if not _to_bool(row.get("tool_correct", "false")):
        error_types.append("tool_error")
        reasons.append(build_tool_reason(row, source_label))
    if not _to_bool(row.get("risk_correct", "false")):
        error_types.append("risk_error")
        reasons.append(
            f"风险等级应为 {row.get('expected_risk', '') or '-'}，实际为 {row.get('actual_risk', '') or '-'}。"
        )
    if not _to_bool(row.get("block_correct", "true")):
        error_types.append("block_error")
        reasons.append(
            f"拦截期望为 {row.get('expected_block', row.get('should_block', '')) or '-'}，实际为 {row.get('actual_block', '') or '-'}。"
        )
    if not _to_bool(row.get("confirmation_correct", "true")):
        error_types.append("confirmation_error")
        reasons.append(
            f"确认期望为 {row.get('expected_need_confirmation', '') or '-'}，实际为 {row.get('actual_need_confirmation', '') or '-'}。"
        )
    if str(row.get("category", "")).endswith("follow_up") and not _to_bool(row.get("task_success", "false")):
        error_types.append("context_error")
        reasons.append("多轮上下文或指代表达未被正确继承。")
    if not _to_bool(row.get("task_success", "false")):
        error_types.append("task_failure")
        reasons.append(f"最终执行状态为 {row.get('execution_status', '') or '-'}，未满足端到端期望。")

    return {
        "id": str(row.get("id", "")),
        "query": str(row.get("query", "")),
        "expected_intent": str(row.get("expected_intent", "")),
        "actual_intent": str(row.get("actual_intent", "")),
        "expected_tools": str(row.get("expected_tools", "")),
        "actual_tools": str(row.get("actual_tools", "")),
        "expected_risk": str(row.get("expected_risk", "")),
        "actual_risk": str(row.get("actual_risk", "")),
        "source": source,
        "error_type": ";".join(dict.fromkeys(error_types)),
        "brief_reason": " | ".join(reasons),
    }


def build_tool_reason(row: dict[str, Any], source_label: str) -> str:
    expected = str(row.get("expected_tools", "") or "-")
    actual = str(row.get("actual_tools", "") or "-")
    query = str(row.get("query", ""))
    if "5000" in query and "check_port_usage" in expected:
        return f"{source_label} 未抽取端口号 5000，工具应为 {expected}，实际为 {actual}。"
    if "入口" in query and "list_open_ports" in expected:
        return f"{source_label} 未把“入口被占住”理解为端口监听/冲突检查，工具应为 {expected}，实际为 {actual}。"
    if "find_large_files" in expected and "find_large_files" not in actual:
        return f"{source_label} 选择了部分磁盘工具但遗漏 find_large_files，导致大文件定位不完整。"
    return f"工具应为 {expected}，实际为 {actual}。"


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() == "true"


if __name__ == "__main__":
    main()
