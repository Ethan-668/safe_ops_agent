from __future__ import annotations

import re
from typing import Any

from agent.prompts import build_planning_messages
from llm.client import LLMClient


DEFAULT_PLAN = {
    "intent": "system_status",
    "risk_level": "low",
    "entities": {},
    "selected_tools": ["get_system_status"],
    "need_confirmation": False,
    "reason": "默认查看系统状态。",
}


class IntentPlanner:
    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    def plan(
        self,
        user_input: str,
        session_state: dict[str, Any],
        tool_specs: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str]:
        messages = build_planning_messages(user_input, session_state, tool_specs)
        llm_plan, source = self.llm_client.plan(messages)
        if llm_plan is not None:
            return self._normalize_plan(llm_plan), source
        fallback = self._fallback_plan(user_input, session_state)
        fallback["reason"] = f"{fallback.get('reason', '')}（{source}）"
        return fallback, "fallback"

    def _normalize_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(DEFAULT_PLAN)
        normalized.update(plan)
        if not isinstance(normalized.get("entities"), dict):
            normalized["entities"] = {}
        normalized["selected_tools"] = self._normalize_selected_tools(normalized.get("selected_tools"))
        normalized["need_confirmation"] = bool(normalized.get("need_confirmation", False))
        return normalized

    def _normalize_selected_tools(self, selected_tools: Any) -> list[str]:
        if not isinstance(selected_tools, list):
            return []

        normalized_tools: list[str] = []
        for item in selected_tools:
            if isinstance(item, str):
                tool_name = item.strip()
            elif isinstance(item, dict):
                tool_name = self._extract_tool_name_from_dict(item)
            else:
                tool_name = ""

            if tool_name:
                normalized_tools.append(tool_name)

        return normalized_tools

    def _extract_tool_name_from_dict(self, item: dict[str, Any]) -> str:
        for key in ("name", "tool", "tool_name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        function_info = item.get("function")
        if isinstance(function_info, dict):
            value = function_info.get("name")
            if isinstance(value, str) and value.strip():
                return value.strip()

        return ""

    def _fallback_plan(self, user_input: str, session_state: dict[str, Any]) -> dict[str, Any]:
        text = user_input.strip().lower()

        if self._is_confirmation(text):
            return {
                "intent": "confirmation",
                "risk_level": session_state.get("pending_risk_level") or "medium",
                "entities": {},
                "selected_tools": [],
                "need_confirmation": False,
                "reason": "识别为二次确认回复。",
            }

        if any(word in text for word in ["清理", "删除临时", "归档", "能归档", "archive", "clean"]):
            selected = ["archive_log_file"] if "归档" in text or "archive" in text else ["safe_clean_tmp"]
            path = self._extract_path(user_input)
            if selected == ["archive_log_file"]:
                path = path or self._extract_log_path_from_context(session_state) or "sandbox/logs"
            return {
                "intent": "safe_file_operation",
                "risk_level": "medium",
                "entities": {"path": path or "sandbox/tmp"},
                "selected_tools": selected,
                "need_confirmation": True,
                "reason": "识别到沙箱文件操作请求，需要二次确认。",
            }

        pid = self._extract_pid(text)
        if pid and any(word in text for word in ["pid", "进程", "process"]):
            return {
                "intent": "process_analysis",
                "risk_level": "low",
                "entities": {"pid": pid},
                "selected_tools": ["check_process_by_pid"],
                "need_confirmation": False,
                "reason": "识别到根据 PID 查询进程状态。",
            }

        port = self._extract_port(text)
        if port:
            return {
                "intent": "network_check",
                "risk_level": "low",
                "entities": {"port": port},
                "selected_tools": ["check_port_usage"],
                "need_confirmation": False,
                "reason": "识别到端口占用查询。",
            }

        if any(word in text for word in ["开放端口", "监听端口", "所有端口", "list ports", "open ports"]):
            return {
                "intent": "network_check",
                "risk_level": "low",
                "entities": {},
                "selected_tools": ["list_open_ports"],
                "need_confirmation": False,
                "reason": "识别到开放端口列表查询。",
            }

        if any(word in text for word in ["磁盘", "空间", "大文件", "占用增长", "异常增长", "df", "du", "disk"]):
            path = self._extract_path(user_input) or "/"
            selected_tools = ["check_disk_usage", "find_large_files"]
            if any(word in text for word in ["使用率", "空间", "df"]):
                selected_tools = ["check_disk_usage"]
            if any(word in text for word in ["大文件", "占空间", "异常增长", "增长", "排查", "top", "du"]):
                selected_tools = ["check_disk_usage", "find_large_files"]
            return {
                "intent": "disk_analysis",
                "risk_level": "low",
                "entities": {"path": path, "top_k": 10, "min_size_mb": 1},
                "selected_tools": selected_tools,
                "need_confirmation": False,
                "reason": "识别到磁盘空间或大文件分析请求。",
            }

        if any(word in text for word in ["进程", "cpu", "卡", "响应慢", "资源占用", "process"]):
            return {
                "intent": "process_analysis",
                "risk_level": "low",
                "entities": {"top_k": 8},
                "selected_tools": ["analyze_process_usage"],
                "need_confirmation": False,
                "reason": "识别到进程资源占用分析请求。",
            }

        if any(word in text for word in ["状态", "负载", "系统", "内核", "uptime", "uname", "内存"]):
            return dict(DEFAULT_PLAN)

        if any(word in text for word in ["日志", "error", "warning", "报错", "异常", "failed", "log"]):
            return {
                "intent": "log_analysis",
                "risk_level": "low",
                "entities": {"keyword": "error|warning|failed", "max_lines": 120},
                "selected_tools": ["analyze_logs"],
                "need_confirmation": False,
                "reason": "识别到日志异常分析请求。",
            }

        if text in {"它", "这个", "刚才那个", "继续", "再看看"}:
            return {
                "intent": "follow_up",
                "risk_level": "low",
                "entities": session_state.get("last_entities", {}),
                "selected_tools": self._tools_for_last_intent(session_state.get("last_intent")),
                "need_confirmation": False,
                "reason": "识别为基于上一轮上下文的追问。",
            }

        return dict(DEFAULT_PLAN)

    def _extract_port(self, text: str) -> int | None:
        patterns = [
            r"端口\s*(\d{1,5})",
            r"(\d{1,5})\s*端口",
            r"port\s*(\d{1,5})",
            r":(\d{1,5})\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                port = int(match.group(1))
                if 1 <= port <= 65535:
                    return port
        return None

    def _extract_pid(self, text: str) -> int | None:
        patterns = [r"\bpid\s*(\d{1,7})\b", r"进程\s*(\d{1,7})"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return None

    def _extract_path(self, text: str) -> str | None:
        match = re.search(r"((?:/|sandbox/|\.\/)[\w./-]+)", text)
        if match:
            return match.group(1)
        return None

    def _is_confirmation(self, text: str) -> bool:
        return text in {"确认", "可以", "可以执行", "执行", "确认执行", "继续", "yes", "y", "ok"}

    def _extract_log_path_from_context(self, session_state: dict[str, Any]) -> str | None:
        tool_results = session_state.get("last_tool_results", {})
        if not isinstance(tool_results, dict):
            return None

        analyze_result = tool_results.get("analyze_logs")
        if isinstance(analyze_result, dict):
            args = analyze_result.get("args", {})
            if isinstance(args, dict):
                log_file = args.get("log_file")
                if isinstance(log_file, str) and log_file:
                    return log_file

        for result in tool_results.values():
            if not isinstance(result, dict):
                continue
            data = result.get("data", {})
            if not isinstance(data, dict):
                continue
            files = data.get("files")
            if isinstance(files, list):
                for item in files:
                    if not isinstance(item, dict):
                        continue
                    path = item.get("path")
                    if isinstance(path, str) and path.startswith("sandbox/logs/"):
                        return path
        return None

    def _tools_for_last_intent(self, last_intent: str | None) -> list[str]:
        return {
            "system_status": ["get_system_status"],
            "disk_analysis": ["check_disk_usage", "find_large_files"],
            "process_analysis": ["analyze_process_usage"],
            "network_check": ["list_open_ports"],
            "log_analysis": ["analyze_logs"],
        }.get(last_intent or "", ["get_system_status"])
