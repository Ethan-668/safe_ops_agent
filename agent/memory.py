from __future__ import annotations

from typing import Any


def new_session_state() -> dict[str, Any]:
    return {
        "last_intent": None,
        "last_entities": {},
        "last_tool_results": {},
        "pending_action": None,
        "pending_tool_call": None,
        "pending_risk_level": None,
        "pending_entities": {},
        "pending_reason": None,
        "history": [],
    }


def update_session_state(
    session_state: dict[str, Any],
    user_input: str,
    plan: dict[str, Any],
    tool_results: list[dict[str, Any]],
    final_answer: str,
    execution_status: str | None = None,
) -> dict[str, Any]:
    session_state["last_intent"] = plan.get("intent")
    session_state["last_entities"] = plan.get("entities", {})
    session_state["last_tool_results"] = {item.get("tool", f"tool_{i}"): item for i, item in enumerate(tool_results)}

    if execution_status == "pending_confirmation" and plan.get("need_confirmation"):
        session_state["pending_action"] = plan.get("intent")
        session_state["pending_tool_call"] = {
            "selected_tools": plan.get("selected_tools", []),
            "entities": plan.get("entities", {}),
        }
        session_state["pending_risk_level"] = plan.get("risk_level")
        session_state["pending_entities"] = plan.get("entities", {})
        session_state["pending_reason"] = plan.get("reason")
    elif execution_status in {"success", "cancelled", "blocked"} or plan.get("intent") != "confirmation":
        session_state["pending_action"] = None
        session_state["pending_tool_call"] = None
        session_state["pending_risk_level"] = None
        session_state["pending_entities"] = {}
        session_state["pending_reason"] = None

    history = session_state.setdefault("history", [])
    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": final_answer})
    session_state["history"] = history[-20:]
    return session_state
