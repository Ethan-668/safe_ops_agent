from __future__ import annotations

from executor.safe_executor import SafeExecutor


def get_system_status(executor: SafeExecutor):
    def handler(_: dict) -> dict:
        commands = {
            "kernel": ["uname", "-a"],
            "uptime": ["uptime"],
            "memory": ["free", "-h"],
        }
        results = {name: executor.run(command) for name, command in commands.items()}
        return {
            "ok": all(result.ok for result in results.values()),
            "tool": "get_system_status",
            "data": {
                name: {
                    "command": result.command,
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                }
                for name, result in results.items()
            },
        }

    return handler
