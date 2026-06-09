from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class AuditLogger:
    def __init__(self, log_path: str | Path) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: dict[str, Any]) -> None:
        safe_record = self._redact(record)
        with self.log_path.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps(safe_record, ensure_ascii=False) + "\n")

    def last_summary(self) -> dict[str, Any]:
        if not self.log_path.exists():
            return {}
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return {}
        if not lines:
            return {}
        try:
            record = json.loads(lines[-1])
        except json.JSONDecodeError:
            return {}
        return {
            "timestamp": record.get("timestamp"),
            "intent": record.get("intent"),
            "risk_level": record.get("risk_level"),
            "selected_tools": record.get("selected_tools"),
            "safety_result": record.get("safety_result"),
            "execution_status": record.get("execution_status"),
            "latency_ms": record.get("latency_ms"),
        }

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "***REDACTED***" if self._is_sensitive_key(key) else self._redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        return value

    def _is_sensitive_key(self, key: str) -> bool:
        lowered = key.lower()
        return any(token in lowered for token in ("api_key", "apikey", "secret", "token", "password"))


def build_audit_record(
    *,
    user_input: str,
    plan: dict[str, Any],
    safety_result: str,
    execution_status: str,
    final_answer: str,
    latency_ms: int,
    model_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_input": user_input,
        "intent": plan.get("intent"),
        "risk_level": plan.get("risk_level"),
        "selected_tools": plan.get("selected_tools", []),
        "entities": plan.get("entities", {}),
        "safety_result": safety_result,
        "execution_status": execution_status,
        "final_answer": final_answer,
        "latency_ms": latency_ms,
    }
    if model_plan is not None:
        record["model_plan"] = model_plan
    return record
