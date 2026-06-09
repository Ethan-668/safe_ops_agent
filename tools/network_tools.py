from __future__ import annotations

from executor.safe_executor import SafeExecutor
from tools.common import parse_int


def check_port_usage(executor: SafeExecutor):
    def handler(args: dict) -> dict:
        port = parse_int(args.get("port"), default=0, minimum=0, maximum=65535)
        if port <= 0:
            return {
                "ok": False,
                "tool": "check_port_usage",
                "args": {"port": args.get("port")},
                "error": "端口参数无效。",
            }
        result = executor.run(["ss", "-ltnp", f"sport = :{port}"])
        if result.returncode == 127:
            result = executor.run(["netstat", "-ltnp"])
            filtered = "\n".join(line for line in result.stdout.splitlines() if f":{port} " in line)
            stdout = filtered
        else:
            stdout = result.stdout
        return {
            "ok": result.ok,
            "tool": "check_port_usage",
            "args": {"port": port},
            "data": {
                "stdout": stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler


def list_open_ports(executor: SafeExecutor):
    def handler(_: dict) -> dict:
        result = executor.run(["ss", "-ltnp"])
        if result.returncode == 127:
            result = executor.run(["netstat", "-ltnp"])
        return {
            "ok": result.ok,
            "tool": "list_open_ports",
            "data": {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler
