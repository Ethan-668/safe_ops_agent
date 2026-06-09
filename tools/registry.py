from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass
class ToolSpec:
    name: str
    description: str
    risk_level: str
    permission: str
    parameters: dict[str, Any]
    handler: ToolHandler | None = None
    implemented: bool = True

    def call(self, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.implemented or self.handler is None:
            return {
                "ok": False,
                "tool": self.name,
                "error": "该工具当前仅保留接口，尚未实现真实操作。",
            }
        return self.handler(args or {})


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def has_tool(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def call(self, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.get(name).call(args)

    def list_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level,
                "permission": tool.permission,
                "parameters": tool.parameters,
                "implemented": tool.implemented,
            }
            for tool in self._tools.values()
        ]
