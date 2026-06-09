from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SANDBOX_ROOT = (PROJECT_ROOT / "sandbox").resolve()
TMP_DIR = (SANDBOX_ROOT / "tmp").resolve()
LOG_DIR = (SANDBOX_ROOT / "logs").resolve()
RECYCLE_DIR = (SANDBOX_ROOT / "recycle_bin").resolve()


def main() -> None:
    ensure_under_project_sandbox(TMP_DIR)
    ensure_under_project_sandbox(LOG_DIR)
    ensure_under_project_sandbox(RECYCLE_DIR)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RECYCLE_DIR.mkdir(parents=True, exist_ok=True)

    clean_recycle_bin()
    write_file(TMP_DIR / "cache_1.tmp", "temporary cache sample 1\n")
    write_file(TMP_DIR / "cache_2.tmp", "temporary cache sample 2\n")
    write_file(
        LOG_DIR / "demo.log",
        "\n".join(
            [
                "2026-06-08 10:00:00 INFO service started",
                "2026-06-08 10:01:00 WARNING disk usage above threshold",
                "2026-06-08 10:02:00 ERROR failed to connect to upstream",
                "",
            ]
        ),
    )
    ensure_gitkeep(TMP_DIR)
    ensure_gitkeep(LOG_DIR)
    ensure_gitkeep(RECYCLE_DIR)
    print("sandbox_reset: ok")


def clean_recycle_bin() -> None:
    for path in RECYCLE_DIR.iterdir():
        ensure_under_project_sandbox(path.resolve())
        if path.name == ".gitkeep":
            continue
        if path.is_dir():
            remove_tree(path)
        elif path.is_file() or path.is_symlink():
            path.unlink()


def remove_tree(path: Path) -> None:
    for child in path.iterdir():
        ensure_under_project_sandbox(child.resolve())
        if child.is_dir():
            remove_tree(child)
        else:
            child.unlink()
    path.rmdir()


def write_file(path: Path, content: str) -> None:
    ensure_under_project_sandbox(path.resolve())
    path.write_text(content, encoding="utf-8")


def ensure_gitkeep(path: Path) -> None:
    write_file(path / ".gitkeep", "")


def ensure_under_project_sandbox(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(SANDBOX_ROOT)
    except ValueError as exc:
        raise RuntimeError(f"refusing to operate outside sandbox: {resolved}") from exc


if __name__ == "__main__":
    main()
