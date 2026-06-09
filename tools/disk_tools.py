from __future__ import annotations

from pathlib import Path

from executor.safe_executor import SafeExecutor
from tools.common import existing_path, parse_int


def check_disk_usage(executor: SafeExecutor):
    def handler(args: dict) -> dict:
        path = existing_path(args.get("path"), "/")
        result = executor.run(["df", "-h", path])
        return {
            "ok": result.ok,
            "tool": "check_disk_usage",
            "args": {"path": path},
            "data": {
                "command": result.command,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler


def find_large_files(executor: SafeExecutor):
    def handler(args: dict) -> dict:
        path = existing_path(args.get("path"), ".")
        top_k = parse_int(args.get("top_k"), default=10, minimum=1, maximum=20)
        min_size_mb = parse_int(args.get("min_size_mb"), default=1, minimum=1, maximum=1024)
        path_obj = Path(path)
        if path_obj.resolve() == Path("/").resolve():
            # Keep the MVP responsive and avoid walking virtual/system trees.
            path = "."

        result = executor.run(
            [
                "find",
                path,
                "-xdev",
                "-type",
                "f",
                "-size",
                f"+{min_size_mb}M",
                "-printf",
                "%s\t%p\n",
            ]
        )
        files: list[dict[str, str | int]] = []
        for line in result.stdout.splitlines():
            try:
                size_raw, file_path = line.split("\t", 1)
                files.append({"size_bytes": int(size_raw), "path": file_path})
            except ValueError:
                continue
        files.sort(key=lambda item: int(item["size_bytes"]), reverse=True)
        return {
            "ok": result.ok,
            "tool": "find_large_files",
            "args": {"path": path, "top_k": top_k, "min_size_mb": min_size_mb},
            "data": {
                "files": files[:top_k],
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            },
        }

    return handler
