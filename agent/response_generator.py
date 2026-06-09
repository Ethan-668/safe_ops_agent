from __future__ import annotations

from typing import Any


def generate_final_answer(
    plan: dict[str, Any],
    safety_status: str,
    execution_status: str,
    tool_results: list[dict[str, Any]],
    blocked_reason: str | None = None,
    plan_source: str = "fallback",
) -> str:
    intent = plan.get("intent", "unknown")
    risk = plan.get("risk_level", "unknown")
    tools = plan.get("selected_tools", [])

    if blocked_reason:
        return (
            f"已拦截该请求。\n\n"
            f"- 识别意图：{intent}\n"
            f"- 风险等级：{risk}\n"
            f"- 安全结果：{safety_status}\n"
            f"- 拦截原因：{blocked_reason}\n\n"
            "我不会执行危险命令、敏感路径写操作或绕过安全规则的请求。"
        )

    if plan.get("need_confirmation"):
        return (
            "该操作属于中风险写操作，将把目标文件移动到 sandbox/recycle_bin，而不是永久删除。是否确认执行？\n\n"
            f"- 识别意图：{intent}\n"
            f"- 风险等级：{risk}\n"
            f"- 计划工具：{', '.join(tools) if tools else '无'}\n"
            f"- 安全校验：{safety_status}\n"
            "- 可回复：确认 / 取消"
        )

    if execution_status == "cancelled":
        return (
            "已取消本次操作，未执行任何写操作。\n\n"
            f"- 识别意图：{intent}\n"
            f"- 风险等级：{risk}\n"
            f"- 原计划工具：{', '.join(tools) if tools else '无'}\n"
            f"- 执行状态：{execution_status}"
        )

    summary = summarize_tool_results(tool_results)
    action_label = "运维操作" if risk == "medium" else "运维查询"
    return (
        f"已完成本次{action_label}。\n\n"
        f"- 识别意图：{intent}\n"
        f"- 风险等级：{risk}\n"
        f"- 调用工具：{', '.join(tools) if tools else '无'}\n"
        f"- 安全校验：{safety_status}\n"
        f"- 执行状态：{execution_status}\n"
        f"- 规划来源：{plan_source}\n\n"
        f"{summary}"
    )


def summarize_tool_results(tool_results: list[dict[str, Any]]) -> str:
    if not tool_results:
        return "没有执行工具。"

    sections = []
    for result in tool_results:
        tool = result.get("tool", "unknown_tool")
        data = result.get("data", {})
        if not result.get("ok", False):
            error = result.get("error") or data.get("stderr") or "工具执行返回异常。"
            sections.append(f"工具 `{tool}` 未成功：{error}")
            continue

        if tool == "get_system_status":
            sections.append(_summarize_system_status(data))
        elif tool == "check_disk_usage":
            sections.append(_summarize_stdout_tool(tool, data.get("stdout", "")))
        elif tool == "find_large_files":
            files = data.get("files", [])
            if files:
                lines = ["大文件 Top 结果："]
                for item in files[:10]:
                    size_mb = int(item["size_bytes"]) / 1024 / 1024
                    lines.append(f"- {size_mb:.1f} MB  {item['path']}")
                sections.append("\n".join(lines))
            else:
                sections.append("未发现超过阈值的大文件，或当前路径没有可读的大文件结果。")
        elif tool == "analyze_process_usage":
            sections.append("CPU/内存占用较高的进程：\n" + "\n".join(data.get("processes", [])[:10]))
        elif tool == "check_process_by_pid":
            sections.append(_summarize_stdout_tool(tool, data.get("stdout", "")))
        elif tool in {"check_port_usage", "list_open_ports"}:
            stdout = data.get("stdout", "")
            sections.append(stdout if stdout else "未发现匹配的监听端口或当前用户无权限查看进程详情。")
        elif tool == "analyze_logs":
            matches = data.get("matches", [])
            if matches:
                sections.append("日志异常匹配：\n" + "\n".join(matches[-10:]))
            else:
                sections.append(data.get("message") or "最近日志中未发现 error/warning/failed 匹配项。")
        elif tool == "safe_clean_tmp":
            sections.append(_summarize_clean_tmp(data))
        elif tool == "archive_log_file":
            sections.append(_summarize_archive_log(data))
        else:
            sections.append(str(result))

    return "\n\n".join(sections)


def _summarize_system_status(data: dict[str, Any]) -> str:
    parts = []
    for name in ("kernel", "uptime", "memory"):
        item = data.get(name, {})
        stdout = item.get("stdout", "")
        if stdout:
            parts.append(f"{name}:\n{stdout}")
    return "\n\n".join(parts)


def _summarize_stdout_tool(tool: str, stdout: str) -> str:
    if stdout:
        return f"`{tool}` 输出：\n{stdout}"
    return f"`{tool}` 未返回可展示输出。"


def _summarize_clean_tmp(data: dict[str, Any]) -> str:
    moved_files = data.get("moved_files", [])
    moved_count = data.get("moved_count", 0)
    total_size = int(data.get("total_size_bytes", 0))
    if not moved_files:
        return data.get("message") or "sandbox/tmp 下没有需要清理的临时文件。"

    lines = [
        data.get("message") or "已完成沙箱临时文件清理。",
        f"移动文件数：{moved_count}",
        f"总大小：{total_size} bytes",
        "移动明细：",
    ]
    for item in moved_files:
        lines.append(f"- {item.get('source')} -> {item.get('target')} ({item.get('size_bytes')} bytes)")
    return "\n".join(lines)


def _summarize_archive_log(data: dict[str, Any]) -> str:
    if not data.get("archived_file"):
        return data.get("message") or "sandbox/logs 下没有可归档的 .log 文件。"
    return (
        f"{data.get('message') or '已完成沙箱日志归档。'}\n"
        f"源文件：{data.get('source_file')}\n"
        f"归档位置：{data.get('archived_file')}\n"
        f"文件大小：{data.get('size_bytes')} bytes"
    )
