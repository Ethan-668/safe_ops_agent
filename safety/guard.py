from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from safety.injection_detector import detect_prompt_injection
from safety.path_policy import contains_sensitive_path, is_write_request
from safety.rules import DANGEROUS_PATTERNS


@dataclass
class SafetyResult:
    allowed: bool
    status: str
    reason: str
    risk_level: str = "low"


class SafetyGuard:
    def __init__(self, tool_registry: Any) -> None:
        self.tool_registry = tool_registry

    def pre_scan(self, user_input: str) -> SafetyResult:
        if _is_benign_security_question(user_input):
            return SafetyResult(True, "pass", "识别为安全解释类问题，未发现执行请求", "low")

        injected, reason = detect_prompt_injection(user_input)
        if injected:
            return SafetyResult(False, "blocked", reason, "forbidden")

        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(user_input):
                return SafetyResult(
                    False,
                    "blocked",
                    f"命中危险命令规则：{pattern.pattern}",
                    "forbidden",
                )

        has_sensitive_path, reason = contains_sensitive_path(user_input)
        if has_sensitive_path and is_write_request(user_input):
            return SafetyResult(False, "blocked", reason, "forbidden")

        return SafetyResult(True, "pass", "未发现输入级安全风险", "low")

    def validate_plan(self, plan: dict[str, Any]) -> SafetyResult:
        selected_tools = plan.get("selected_tools") or []
        if not isinstance(selected_tools, list):
            return SafetyResult(False, "blocked", "selected_tools 必须是列表", "forbidden")

        for tool_name in selected_tools:
            if not isinstance(tool_name, str) or not tool_name.strip():
                return SafetyResult(False, "blocked", "selected_tools 中存在非法工具名", "forbidden")
            tool_name = tool_name.strip()
            if not self.tool_registry.has_tool(tool_name):
                return SafetyResult(False, "blocked", f"工具不在白名单中：{tool_name}", "forbidden")
            tool = self.tool_registry.get(tool_name)
            if tool.risk_level in {"high", "forbidden"}:
                return SafetyResult(False, "blocked", f"工具风险等级禁止执行：{tool_name}", "forbidden")
            if not tool.implemented:
                return SafetyResult(False, "not_implemented", f"工具暂未实现：{tool_name}", tool.risk_level)

        entities = plan.get("entities") or {}
        if isinstance(entities, dict):
            for key in ("path", "file", "target_path", "log_path"):
                value = entities.get(key)
                if isinstance(value, str):
                    has_sensitive_path, reason = contains_sensitive_path(value)
                    if has_sensitive_path and plan.get("risk_level") != "low":
                        return SafetyResult(False, "blocked", reason, "forbidden")

        return SafetyResult(True, "pass", "工具与参数通过安全校验", plan.get("risk_level", "low"))


def _is_benign_security_question(text: str) -> bool:
    lowered = text.lower()
    benign_markers = (
        "为什么",
        "为何",
        "解释",
        "说明",
        "风险是什么",
        "有什么风险",
        "能否介绍",
        "介绍一下",
        "了解",
        "不要执行",
        "不执行",
        "只解释",
        "只说明",
    )
    if not any(marker in lowered for marker in benign_markers):
        return False

    execution_markers = (
        "直接执行",
        "马上执行",
        "立即执行",
        "执行危险命令",
        "输出计划后马上执行",
        "顺便删除",
        "顺便删掉",
        "把 ",
        "帮我删除",
        "帮我删掉",
        "清空 ",
        "修改 ",
        "覆盖 ",
        "chmod ",
        "curl ",
        "| bash",
        "| sh",
    )
    return not any(marker in lowered for marker in execution_markers)
