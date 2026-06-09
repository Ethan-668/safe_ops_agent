from __future__ import annotations

import json
import os
from typing import Any

import gradio as gr

from agent.planner import SafeOpsAgent


agent = SafeOpsAgent()


def handle_message(
    message: str,
    chat_history: list[dict[str, str]] | None,
    session_state: dict[str, Any] | None,
):
    chat_history = chat_history or []
    session_state = session_state or agent.new_state()
    result = agent.handle(message, session_state)
    chat_history.append({"role": "user", "content": message})
    chat_history.append({"role": "assistant", "content": result["answer"]})
    status = result["status"]
    audit_summary = result["audit_summary"]
    return (
        "",
        chat_history,
        result["state"],
        status.get("intent", "-"),
        status.get("risk_level", "-"),
        status.get("selected_tools", "-"),
        status.get("safety_result", "-"),
        status.get("execution_status", "-"),
        json.dumps(audit_summary, ensure_ascii=False, indent=2),
    )


def clear_session():
    return [], agent.new_state(), "-", "-", "-", "-", "-", "{}"


with gr.Blocks(title="安全智能运维 Agent") as demo:
    gr.Markdown("## 安全智能运维 Agent")
    gr.Markdown("基于 API 大模型 / 规则 fallback / 类 MCP 工具注册中心 / 安全护栏的第一阶段 MVP。")

    session_state = gr.State(agent.new_state())

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(label="多轮对话", height=520)
            user_input = gr.Textbox(
                label="用户输入",
                placeholder="例如：帮我看看磁盘为什么快满了",
                lines=2,
            )
            with gr.Row():
                submit_btn = gr.Button("发送", variant="primary")
                clear_btn = gr.Button("清空会话")

        with gr.Column(scale=2):
            gr.Markdown("### Agent 状态")
            current_intent = gr.Textbox(label="当前意图", interactive=False)
            risk_level = gr.Textbox(label="风险等级", interactive=False)
            selected_tools = gr.Textbox(label="调用工具", interactive=False)
            safety_result = gr.Textbox(label="安全校验结果", interactive=False)
            execution_status = gr.Textbox(label="执行状态", interactive=False)
            audit_summary = gr.Code(label="最近一次审计日志摘要", language="json", interactive=False)

    outputs = [
        user_input,
        chatbot,
        session_state,
        current_intent,
        risk_level,
        selected_tools,
        safety_result,
        execution_status,
        audit_summary,
    ]

    submit_btn.click(handle_message, [user_input, chatbot, session_state], outputs)
    user_input.submit(handle_message, [user_input, chatbot, session_state], outputs)
    clear_btn.click(
        clear_session,
        None,
        [
            chatbot,
            session_state,
            current_intent,
            risk_level,
            selected_tools,
            safety_result,
            execution_status,
            audit_summary,
        ],
    )


if __name__ == "__main__":
    server_name = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    demo.launch(server_name=server_name, server_port=server_port)
