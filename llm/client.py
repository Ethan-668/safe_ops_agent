from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_DOTENV = PROJECT_ROOT / ".env"
LLM_ENV_KEYS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_NAME")


def load_local_dotenv() -> None:
    """Load a local .env file when python-dotenv is installed.

    Existing process environment variables keep priority, and no values are
    printed or returned from this helper.
    """

    dotenv_path = PROJECT_DOTENV
    if dotenv_path.exists():
        _load_env_values(dotenv_path)
        return

    try:
        from dotenv import find_dotenv
    except ImportError:
        return

    discovered = find_dotenv(usecwd=True)
    if discovered:
        _load_env_values(Path(discovered))


def get_llm_env_diagnostics(force_fallback: bool = False) -> dict[str, bool]:
    """Return non-sensitive LLM configuration diagnostics."""

    load_local_dotenv()
    return {
        "env_file_exists": PROJECT_DOTENV.exists(),
        "api_key_set": bool(os.getenv("LLM_API_KEY", "").strip()),
        "base_url_set": bool(os.getenv("LLM_BASE_URL", "").strip()),
        "model_name_set": bool(os.getenv("LLM_MODEL_NAME", "").strip()),
        "force_fallback": force_fallback,
    }


def _load_env_values(path: Path) -> None:
    try:
        from dotenv import dotenv_values
    except ImportError:
        _load_env_values_fallback(path)
        return

    for key, value in dotenv_values(dotenv_path=path).items():
        if key and value is not None and not os.getenv(key, "").strip():
            os.environ[key] = value


def _load_env_values_fallback(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if key not in LLM_ENV_KEYS and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        if os.getenv(key, "").strip():
            continue
        os.environ[key] = _strip_env_value(value)


def _strip_env_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


class LLMClient:
    """OpenAI-compatible chat completion client.

    The client intentionally reads credentials only from environment variables
    and never exposes them to audit logs or UI state.
    """

    def __init__(self) -> None:
        load_local_dotenv()
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
        self.model_name = os.getenv("LLM_MODEL_NAME", "").strip()
        self.last_error_type = ""
        self.error_types: list[str] = []

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url and self.model_name)

    def plan(self, messages: list[dict[str, str]], timeout_seconds: int = 20) -> tuple[dict[str, Any] | None, str]:
        if not self.is_configured:
            self._record_error("MissingConfig")
            return None, "LLM 环境变量未完整配置，使用规则 fallback。"

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return self._parse_json(content), "llm"
        except Exception as exc:  # noqa: BLE001 - fall back safely for demos.
            error_type = exc.__class__.__name__
            self._record_error(error_type)
            return None, f"LLM 调用失败，使用规则 fallback：{error_type}"

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
            if not match:
                match = re.search(r"(\{.*\})", content, re.DOTALL)
            if not match:
                raise
            parsed = json.loads(match.group(1))
        if not isinstance(parsed, dict):
            raise ValueError("LLM response is not a JSON object")
        return parsed

    def _record_error(self, error_type: str) -> None:
        self.last_error_type = error_type
        self.error_types.append(error_type)
