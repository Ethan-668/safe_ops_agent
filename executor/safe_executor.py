from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Sequence


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timeout: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timeout


class SafeExecutor:
    """Run fixed command argument lists without invoking a shell."""

    def __init__(self, timeout_seconds: int = 8, max_output_chars: int = 12000) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def run(self, command: Sequence[str]) -> CommandResult:
        if not command:
            raise ValueError("command must not be empty")
        if not all(isinstance(part, str) and part for part in command):
            raise ValueError("command must be a sequence of non-empty strings")

        try:
            completed = subprocess.run(
                list(command),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )
            return CommandResult(
                command=list(command),
                returncode=completed.returncode,
                stdout=self._trim(completed.stdout),
                stderr=self._trim(completed.stderr),
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=list(command),
                returncode=124,
                stdout=self._trim(exc.stdout or ""),
                stderr=f"command timed out after {self.timeout_seconds}s",
                timeout=True,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                command=list(command),
                returncode=127,
                stdout="",
                stderr=str(exc),
            )

    def _trim(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "\n...[output truncated]"
