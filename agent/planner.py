from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from agent.audit import AuditLogger, build_audit_record
from agent.memory import new_session_state, update_session_state
from agent.nlu import IntentPlanner
from agent.response_generator import generate_final_answer
from executor.safe_executor import SafeExecutor
from llm.client import LLMClient
from safety.guard import SafetyGuard, SafetyResult
from tools.disk_tools import check_disk_usage, find_large_files
from tools.log_tools import analyze_logs
from tools.network_tools import check_port_usage, list_open_ports
from tools.process_tools import analyze_process_usage, check_process_by_pid
from tools.registry import ToolRegistry, ToolSpec
from tools.sandbox_tools import archive_log_file, safe_clean_tmp
from tools.system_tools import get_system_status


class SafeOpsAgent:
    def __init__(
        self,
        sandbox_root: str | Path = "sandbox",
        audit_log_path: str | Path = "logs/audit.jsonl",
        llm_client: LLMClient | None = None,
    ) -> None:
        self.sandbox_root = Path(sandbox_root)
        self.sandbox_log_dir = self.sandbox_root / "logs"
        self.executor = SafeExecutor()
        self.registry = build_tool_registry(self.executor, self.sandbox_log_dir)
        self.guard = SafetyGuard(self.registry)
        self.intent_planner = IntentPlanner(llm_client or LLMClient())
        self.audit_logger = AuditLogger(audit_log_path)

    def new_state(self) -> dict[str, Any]:
        return new_session_state()

    def handle(self, user_input: str, session_state: dict[str, Any] | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        state = session_state or self.new_state()
        user_input = user_input.strip()

        if not user_input:
            final_answer = "请输入需要诊断的运维问题。"
            return {
                "answer": final_answer,
                "state": state,
                "status": self._status_payload(
                    plan={},
                    safety_status="skip",
                    execution_status="empty_input",
                    latency_ms=0,
                ),
                "audit_summary": self.audit_logger.last_summary(),
            }

        plan: dict[str, Any] = {
            "intent": "unknown",
            "risk_level": "low",
            "entities": {},
            "selected_tools": [],
            "need_confirmation": False,
            "reason": "",
        }
        plan_source = "fallback"
        tool_results: list[dict[str, Any]] = []

        pre_scan = self.guard.pre_scan(user_input)
        if not pre_scan.allowed:
            plan_source = "safety_rule"
            if state.get("pending_action"):
                pending_call = state.get("pending_tool_call") or {}
                plan.update(
                    {
                        "intent": "prompt_injection" if "注入" in pre_scan.reason else "dangerous_operation",
                        "risk_level": pre_scan.risk_level,
                        "entities": state.get("pending_entities") or pending_call.get("entities", {}),
                        "selected_tools": pending_call.get("selected_tools", []),
                        "reason": f"确认阶段输入命中安全规则，已取消待确认操作：{pre_scan.reason}",
                    }
                )
            else:
                plan.update(
                    {
                        "intent": "prompt_injection" if "注入" in pre_scan.reason else "dangerous_operation",
                        "risk_level": pre_scan.risk_level,
                        "selected_tools": [],
                        "reason": pre_scan.reason,
                    }
                )
            execution_status = "blocked"
            final_answer = generate_final_answer(
                plan,
                pre_scan.status,
                execution_status,
                tool_results,
                blocked_reason=pre_scan.reason,
                plan_source=plan_source,
            )
            return self._finish(
                user_input=user_input,
                state=state,
                plan=plan,
                tool_results=tool_results,
                final_answer=final_answer,
                safety_result=pre_scan,
                execution_status=execution_status,
                started=started,
                plan_source=plan_source,
            )

        if state.get("pending_action") and self._is_cancel_input(user_input):
            pending_call = state.get("pending_tool_call") or {}
            plan.update(
                {
                    "intent": "confirmation",
                    "risk_level": state.get("pending_risk_level") or "medium",
                    "entities": state.get("pending_entities") or pending_call.get("entities", {}),
                    "selected_tools": pending_call.get("selected_tools", []),
                    "reason": "用户取消待确认操作。",
                }
            )
            execution_status = "cancelled"
            safety_result = SafetyResult(True, "cancelled", "用户取消待确认操作", plan["risk_level"])
            final_answer = generate_final_answer(
                plan,
                safety_result.status,
                execution_status,
                tool_results,
                plan_source=plan_source,
            )
            return self._finish(
                user_input=user_input,
                state=state,
                plan=plan,
                tool_results=tool_results,
                final_answer=final_answer,
                safety_result=safety_result,
                execution_status=execution_status,
                started=started,
                plan_source=plan_source,
            )

        if state.get("pending_action") and self._is_confirm_input(user_input):
            pending_call = state.get("pending_tool_call") or {}
            plan.update(
                {
                    "intent": state.get("pending_action") or "safe_file_operation",
                    "risk_level": state.get("pending_risk_level") or "medium",
                    "entities": state.get("pending_entities") or pending_call.get("entities", {}),
                    "selected_tools": pending_call.get("selected_tools", []),
                    "need_confirmation": False,
                    "reason": state.get("pending_reason") or "用户已确认执行待确认操作。",
                }
            )
            plan_validation = self.guard.validate_plan(plan)
            if not plan_validation.allowed:
                execution_status = "blocked"
                final_answer = generate_final_answer(
                    plan,
                    plan_validation.status,
                    execution_status,
                    tool_results,
                    blocked_reason=plan_validation.reason,
                    plan_source=plan_source,
                )
                return self._finish(
                    user_input=user_input,
                    state=state,
                    plan=plan,
                    tool_results=tool_results,
                    final_answer=final_answer,
                    safety_result=plan_validation,
                    execution_status=execution_status,
                    started=started,
                    plan_source=plan_source,
                )

            for tool_name in plan.get("selected_tools", []):
                tool_results.append(self.registry.call(tool_name, plan.get("entities", {})))

            execution_status = "success" if all(result.get("ok", False) for result in tool_results) else "partial_failure"
            final_answer = generate_final_answer(
                plan,
                plan_validation.status,
                execution_status,
                tool_results,
                plan_source=plan_source,
            )
            return self._finish(
                user_input=user_input,
                state=state,
                plan=plan,
                tool_results=tool_results,
                final_answer=final_answer,
                safety_result=plan_validation,
                execution_status=execution_status,
                started=started,
                plan_source=plan_source,
            )

        plan, plan_source = self.intent_planner.plan(user_input, state, self.registry.list_specs())
        if self._requires_confirmation(plan):
            plan["risk_level"] = "medium"
            plan["need_confirmation"] = True
        plan_validation = self.guard.validate_plan(plan)

        if plan.get("need_confirmation"):
            if not plan_validation.allowed:
                execution_status = "blocked"
                final_answer = generate_final_answer(
                    plan,
                    plan_validation.status,
                    execution_status,
                    tool_results,
                    blocked_reason=plan_validation.reason,
                    plan_source=plan_source,
                )
                return self._finish(
                    user_input=user_input,
                    state=state,
                    plan=plan,
                    tool_results=tool_results,
                    final_answer=final_answer,
                    safety_result=plan_validation,
                    execution_status=execution_status,
                    started=started,
                    plan_source=plan_source,
                )

            execution_status = "pending_confirmation"
            final_answer = generate_final_answer(
                plan,
                "need_confirmation",
                execution_status,
                tool_results,
                plan_source=plan_source,
            )
            pending_safety = SafetyResult(
                True,
                "need_confirmation",
                plan_validation.reason,
                plan_validation.risk_level,
            )
            return self._finish(
                user_input=user_input,
                state=state,
                plan=plan,
                tool_results=tool_results,
                final_answer=final_answer,
                safety_result=pending_safety,
                execution_status=execution_status,
                started=started,
                plan_source=plan_source,
            )

        if not plan_validation.allowed:
            execution_status = "blocked"
            final_answer = generate_final_answer(
                plan,
                plan_validation.status,
                execution_status,
                tool_results,
                blocked_reason=plan_validation.reason,
                plan_source=plan_source,
            )
            return self._finish(
                user_input=user_input,
                state=state,
                plan=plan,
                tool_results=tool_results,
                final_answer=final_answer,
                safety_result=plan_validation,
                execution_status=execution_status,
                started=started,
                plan_source=plan_source,
            )

        for tool_name in plan.get("selected_tools", []):
            tool_results.append(self.registry.call(tool_name, plan.get("entities", {})))

        execution_status = "success" if all(result.get("ok", False) for result in tool_results) else "partial_failure"
        final_answer = generate_final_answer(
            plan,
            plan_validation.status,
            execution_status,
            tool_results,
            plan_source=plan_source,
        )
        return self._finish(
            user_input=user_input,
            state=state,
            plan=plan,
            tool_results=tool_results,
            final_answer=final_answer,
            safety_result=plan_validation,
            execution_status=execution_status,
            started=started,
            plan_source=plan_source,
        )

    def _finish(
        self,
        *,
        user_input: str,
        state: dict[str, Any],
        plan: dict[str, Any],
        tool_results: list[dict[str, Any]],
        final_answer: str,
        safety_result: SafetyResult,
        execution_status: str,
        started: float,
        plan_source: str,
    ) -> dict[str, Any]:
        latency_ms = int((time.perf_counter() - started) * 1000)
        state = update_session_state(state, user_input, plan, tool_results, final_answer, execution_status)
        audit_record = build_audit_record(
            user_input=user_input,
            plan=plan,
            safety_result=safety_result.status,
            execution_status=execution_status,
            final_answer=final_answer,
            latency_ms=latency_ms,
            model_plan={
                "source": plan_source,
                "plan": plan,
                "safety_reason": safety_result.reason,
            },
        )
        self.audit_logger.write(audit_record)
        return {
            "answer": final_answer,
            "state": state,
            "status": self._status_payload(plan, safety_result.status, execution_status, latency_ms, plan_source),
            "audit_summary": self.audit_logger.last_summary(),
        }

    def _status_payload(
        self,
        plan: dict[str, Any],
        safety_status: str,
        execution_status: str,
        latency_ms: int,
        plan_source: str | None = None,
    ) -> dict[str, Any]:
        return {
            "intent": plan.get("intent", "-"),
            "risk_level": plan.get("risk_level", "-"),
            "selected_tools": ", ".join(plan.get("selected_tools", []) or []) or "-",
            "safety_result": safety_status,
            "execution_status": execution_status,
            "latency_ms": latency_ms,
            "source": plan_source or "-",
        }

    def _is_confirm_input(self, text: str) -> bool:
        normalized = text.strip().lower()
        return normalized in {"确认", "可以", "可以执行", "执行", "确认执行", "yes", "y", "ok"}

    def _is_cancel_input(self, text: str) -> bool:
        normalized = text.strip().lower()
        return normalized in {"取消", "不要", "不执行", "别执行", "算了", "cancel", "no", "n"}

    def _requires_confirmation(self, plan: dict[str, Any]) -> bool:
        for tool_name in plan.get("selected_tools", []) or []:
            if not isinstance(tool_name, str) or not self.registry.has_tool(tool_name):
                continue
            tool = self.registry.get(tool_name)
            if tool.risk_level == "medium":
                return True
        return False


def build_tool_registry(executor: SafeExecutor, sandbox_log_dir: Path) -> ToolRegistry:
    sandbox_root = sandbox_log_dir.parent
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_system_status",
            description="获取系统内核、运行时间、负载和内存信息",
            risk_level="low",
            permission="read_only",
            parameters={},
            handler=get_system_status(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="check_disk_usage",
            description="查看指定路径所在文件系统的磁盘使用情况",
            risk_level="low",
            permission="read_only",
            parameters={"path": {"type": "string", "default": "/"}},
            handler=check_disk_usage(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="find_large_files",
            description="查找指定路径下较大的普通文件",
            risk_level="low",
            permission="read_only",
            parameters={
                "path": {"type": "string", "default": "."},
                "top_k": {"type": "integer", "default": 10},
                "min_size_mb": {"type": "integer", "default": 1},
            },
            handler=find_large_files(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="analyze_process_usage",
            description="查看 CPU 占用较高的进程",
            risk_level="low",
            permission="read_only",
            parameters={"top_k": {"type": "integer", "default": 8}},
            handler=analyze_process_usage(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="check_process_by_pid",
            description="根据 PID 查看进程状态",
            risk_level="low",
            permission="read_only",
            parameters={"pid": {"type": "integer"}},
            handler=check_process_by_pid(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="check_port_usage",
            description="检查指定端口是否被监听进程占用",
            risk_level="low",
            permission="read_only",
            parameters={"port": {"type": "integer"}},
            handler=check_port_usage(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="list_open_ports",
            description="列出当前监听中的 TCP 端口",
            risk_level="low",
            permission="read_only",
            parameters={},
            handler=list_open_ports(executor),
        )
    )
    registry.register(
        ToolSpec(
            name="analyze_logs",
            description="分析沙箱日志或系统可读日志中的 error/warning/failed",
            risk_level="low",
            permission="read_only",
            parameters={
                "keyword": {"type": "string", "default": "error|warning|failed"},
                "max_lines": {"type": "integer", "default": 120},
            },
            handler=analyze_logs(executor, sandbox_log_dir),
        )
    )
    registry.register(
        ToolSpec(
            name="safe_clean_tmp",
            description="清理沙箱 tmp 目录，将文件移动到 recycle_bin，不永久删除",
            risk_level="medium",
            permission="sandbox_write",
            parameters={"path": {"type": "string", "default": "sandbox/tmp"}},
            handler=safe_clean_tmp(sandbox_root),
            implemented=True,
        )
    )
    registry.register(
        ToolSpec(
            name="archive_log_file",
            description="归档沙箱 logs 目录下的日志文件，将文件移动到 recycle_bin",
            risk_level="medium",
            permission="sandbox_write",
            parameters={"path": {"type": "string", "default": "sandbox/logs"}},
            handler=archive_log_file(sandbox_root),
            implemented=True,
        )
    )
    return registry
