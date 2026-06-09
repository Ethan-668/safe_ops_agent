from __future__ import annotations

from executor.safe_executor import SafeExecutor
from tools.common import parse_int


def analyze_process_usage(executor: SafeExecutor):
    def handler(args: dict) -> dict:
        top_k = parse_int(args.get("top_k"), default=8, minimum=1, maximum=20)
        result = executor.run(["ps", "-eo", "pid,ppid,comm,%cpu,%mem,args", "--sort=-%cpu"])
        lines = result.stdout.splitlines()
        selected = lines[: top_k + 1] if lines else []
        return {
            "ok": result.ok,
            "tool": "analyze_process_usage",
            "args": {"top_k": top_k},
            "data": {
                "processes": selected,
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler


def check_process_by_pid(executor: SafeExecutor):
    def handler(args: dict) -> dict:
        pid = parse_int(args.get("pid"), default=0, minimum=0, maximum=9999999)
        if pid <= 0:
            return {
                "ok": False,
                "tool": "check_process_by_pid",
                "args": {"pid": args.get("pid")},
                "error": "PID 参数无效。",
            }
        result = executor.run(["ps", "-p", str(pid), "-o", "pid,ppid,comm,%cpu,%mem,args"])
        return {
            "ok": result.ok,
            "tool": "check_process_by_pid",
            "args": {"pid": pid},
            "data": {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler
