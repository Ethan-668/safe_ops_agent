from __future__ import annotations

from pathlib import Path

from executor.safe_executor import SafeExecutor
from tools.common import parse_int


def analyze_logs(executor: SafeExecutor, sandbox_log_dir: Path):
    def handler(args: dict) -> dict:
        max_lines = parse_int(args.get("max_lines"), default=120, minimum=20, maximum=500)
        keyword = args.get("keyword") if isinstance(args.get("keyword"), str) else "error|warning|failed"
        candidates = sorted(sandbox_log_dir.glob("*.log"))
        if candidates:
            log_file = str(candidates[-1])
            tail_result = executor.run(["tail", "-n", str(max_lines), log_file])
        else:
            log_file = "/var/log/syslog"
            if not Path(log_file).exists():
                log_file = "/var/log/messages"
            if Path(log_file).exists():
                tail_result = executor.run(["tail", "-n", str(max_lines), log_file])
            else:
                return {
                    "ok": True,
                    "tool": "analyze_logs",
                    "args": {"max_lines": max_lines},
                    "data": {"matches": [], "message": "未找到可读取的沙箱日志或系统日志。"},
                }

        lowered_keywords = [part.strip().lower() for part in keyword.split("|") if part.strip()]
        matches = [
            line
            for line in tail_result.stdout.splitlines()
            if any(part in line.lower() for part in lowered_keywords)
        ]
        return {
            "ok": tail_result.ok,
            "tool": "analyze_logs",
            "args": {"log_file": log_file, "max_lines": max_lines, "keyword": keyword},
            "data": {
                "matches": matches[-30:],
                "match_count": len(matches),
                "stderr": tail_result.stderr.strip(),
                "returncode": tail_result.returncode,
            },
        }

    return handler
