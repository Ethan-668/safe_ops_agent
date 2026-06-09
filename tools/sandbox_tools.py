from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import shutil
from typing import Any

from safety.path_policy import is_under_directory


def safe_clean_tmp(sandbox_root: Path):
    project_root = sandbox_root.parent.resolve()
    tmp_dir = (sandbox_root / "tmp").resolve()
    recycle_dir = (sandbox_root / "recycle_bin").resolve()

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        tmp_dir.mkdir(parents=True, exist_ok=True)
        recycle_dir.mkdir(parents=True, exist_ok=True)

        requested_path = _resolve_requested_path(args.get("path") or "sandbox/tmp", project_root)
        if requested_path != tmp_dir:
            return {
                "ok": False,
                "tool": "safe_clean_tmp",
                "error": "安全策略拒绝：safe_clean_tmp 只能清理项目 sandbox/tmp 目录。",
                "args": {"path": str(requested_path)},
            }

        movable_files = [
            path
            for path in sorted(tmp_dir.iterdir())
            if _is_regular_visible_file(path)
        ]
        if not movable_files:
            return {
                "ok": True,
                "tool": "safe_clean_tmp",
                "args": {"path": str(tmp_dir)},
                "data": {
                    "message": "sandbox/tmp 下没有需要清理的临时文件。",
                    "moved_files": [],
                    "moved_count": 0,
                    "total_size_bytes": 0,
                    "recycle_bin": str(recycle_dir),
                },
            }

        moved_files = []
        total_size = 0
        for source in movable_files:
            if not is_under_directory(source, tmp_dir):
                return {
                    "ok": False,
                    "tool": "safe_clean_tmp",
                    "error": f"安全策略拒绝：路径逃逸风险 {source}",
                }

            size = source.stat().st_size
            target = _timestamped_target(recycle_dir, source.name)
            shutil.move(str(source), str(target))
            total_size += size
            moved_files.append(
                {
                    "source": str(source),
                    "target": str(target),
                    "size_bytes": size,
                }
            )

        return {
            "ok": True,
            "tool": "safe_clean_tmp",
            "args": {"path": str(tmp_dir)},
            "data": {
                "message": "已将 sandbox/tmp 下的临时文件移动到 sandbox/recycle_bin。",
                "moved_files": moved_files,
                "moved_count": len(moved_files),
                "total_size_bytes": total_size,
                "recycle_bin": str(recycle_dir),
            },
        }

    return handler


def archive_log_file(sandbox_root: Path):
    project_root = sandbox_root.parent.resolve()
    log_dir = (sandbox_root / "logs").resolve()
    recycle_dir = (sandbox_root / "recycle_bin").resolve()

    def handler(args: dict[str, Any]) -> dict[str, Any]:
        log_dir.mkdir(parents=True, exist_ok=True)
        recycle_dir.mkdir(parents=True, exist_ok=True)

        requested = args.get("log_path") or args.get("file") or args.get("path")
        if requested:
            requested_path = _resolve_requested_path(requested, project_root)
            if requested_path == log_dir:
                source = _select_largest_log(log_dir)
            else:
                source = requested_path
        else:
            source = _select_largest_log(log_dir)

        if source is None:
            return {
                "ok": True,
                "tool": "archive_log_file",
                "args": {"path": str(log_dir)},
                "data": {
                    "message": "sandbox/logs 下没有可归档的 .log 文件。",
                    "archived_file": None,
                    "size_bytes": 0,
                },
            }

        source = source.resolve()
        if not is_under_directory(source, log_dir):
            return {
                "ok": False,
                "tool": "archive_log_file",
                "error": "安全策略拒绝：archive_log_file 只能归档 sandbox/logs 下的日志文件。",
                "args": {"path": str(source)},
            }
        if not _is_regular_visible_file(source) or source.suffix != ".log":
            return {
                "ok": False,
                "tool": "archive_log_file",
                "error": "安全策略拒绝：只能归档 sandbox/logs 下存在的 .log 文件。",
                "args": {"path": str(source)},
            }

        size = source.stat().st_size
        target = _timestamped_target(recycle_dir, source.name)
        shutil.move(str(source), str(target))
        return {
            "ok": True,
            "tool": "archive_log_file",
            "args": {"path": str(source)},
            "data": {
                "message": "已将沙箱日志移动到 sandbox/recycle_bin 完成归档。",
                "archived_file": str(target),
                "source_file": str(source),
                "size_bytes": size,
                "recycle_bin": str(recycle_dir),
            },
        }

    return handler


def _resolve_requested_path(value: Any, project_root: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        return project_root
    path_text = _extract_path_fragment(value.strip()) or value.strip()
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return path.resolve()


def _extract_path_fragment(text: str) -> str | None:
    match = re.search(r"((?:/|sandbox/|\.\/)[\w./-]+)", text)
    if match:
        return match.group(1)
    return None


def _timestamped_target(recycle_dir: Path, original_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    original = Path(original_name)
    if original.suffix:
        candidate = recycle_dir / f"{original.stem}_{timestamp}{original.suffix}"
    else:
        candidate = recycle_dir / f"{original.name}_{timestamp}"

    counter = 1
    while candidate.exists():
        if original.suffix:
            candidate = recycle_dir / f"{original.stem}_{timestamp}_{counter}{original.suffix}"
        else:
            candidate = recycle_dir / f"{original.name}_{timestamp}_{counter}"
        counter += 1
    return candidate


def _select_largest_log(log_dir: Path) -> Path | None:
    candidates = [path for path in log_dir.glob("*.log") if _is_regular_visible_file(path)]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def _is_regular_visible_file(path: Path) -> bool:
    return path.is_file() and path.name != ".gitkeep" and not path.name.startswith(".")
