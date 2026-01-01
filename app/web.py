import gradio as gr
import sys
import os
from langchain_core.messages import AIMessage, HumanMessage

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
try:
    from rag.src.query import ask_question
except ImportError:
    sys.path.append("C:/Users/Administrator/Desktop/financial agent")
    from rag.src.query import ask_question


def gradio_chat(message, history):
    if not message:
        return "", history or []

    chat_history_messages = []

    if history:
        if isinstance(history[0], dict):
            for msg in history:
                role = msg.get("role")
                content = msg.get("content")
                if role == "user" and content:
                    chat_history_messages.append(HumanMessage(content=content))
                elif role == "assistant" and content:
                    chat_history_messages.append(AIMessage(content=content))
        elif isinstance(history[0], (list, tuple)):
            for pair in history:
                if len(pair) >= 1 and pair[0]:
                    chat_history_messages.append(HumanMessage(content=pair[0]))
                if len(pair) >= 2 and pair[1]:
                    chat_history_messages.append(AIMessage(content=pair[1]))

    try:
        answer, new_chat_history_messages, _ = ask_question(
            question=message,
            chat_history_messages=chat_history_messages,
            chat_history_str=""
        )
    except Exception as e:
        answer = f"系统出错：{str(e)}"
        new_chat_history_messages = chat_history_messages + [
            HumanMessage(content=message),
            AIMessage(content=answer)
        ]

    new_history_dict = []
    for msg in new_chat_history_messages:
        if isinstance(msg, HumanMessage):
            new_history_dict.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            new_history_dict.append({"role": "assistant", "content": msg.content})

    if message.strip().lower() == "q":
        new_history_dict = [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "感谢咨询，祝您生活愉快!"}
        ]

    return "", new_history_dict


# ✅ 使用 Gradio 官方主题 + 自定义微调（避免冲突）
custom_css = """
/* 修复消息气泡错位 —— 关键！ */
.gradio-container .chatbot {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* 用户消息：右对齐 */
.chatbot .message.user {
    align-self: flex-end;
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white;
    border-radius: 16px 16px 4px 16px;
    padding: 12px 18px;
    max-width: 70%;
    margin-left: auto;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.2);
}

/* 助手消息：左对齐 */
.chatbot .message.assistant {
    align-self: flex-start;
    background: white;
    color: #1a202c;
    border: 1px solid #e2e8f0;
    border-radius: 16px 16px 16px 4px;
    padding: 12px 18px;
    max-width: 70%;
    margin-right: auto;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 输入框：单行、横排 */
.textbox {
    font-size: 15px;
    padding: 12px 18px;
    border-radius: 20px;
    border: 1px solid #cbd5e0;
    background: white;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.textbox:focus {
    outline: none;
    border-color: #3182ce;
    box-shadow: 0 0 0 2px rgba(49, 130, 206, 0.2);
}

/* 按钮：圆角胶囊 */
.button-primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    color: white;
    border: none;
    border-radius: 20px;
    padding: 10px 20px;
    font-size: 14px;
    box-shadow: 0 2px 6px rgba(37, 99, 235, 0.3);
}

.button-clear {
    background: #f8fafc;
    color: #4a5568;
    border: 1px solid #cbd5e0;
    border-radius: 20px;
    padding: 10px 20px;
    font-size: 14px;
}
"""

with gr.Blocks(
    title="金融顾问 RAG 系统",
    css=custom_css,
    theme=gr.themes.Soft(primary_hue="blue"),
    fill_height=True
) as demo:
    gr.Markdown("# 📊 金融顾问 RAG 系统")
    gr.Markdown("基于2019–2021年基金数据与招股说明书 · 输入 `q` 结束对话")

    chatbot = gr.Chatbot(height=550)

    with gr.Row():
        msg = gr.Textbox(
            placeholder="请输入您的问题（按 Enter 发送）...",
            lines=1,
            max_lines=1,
            scale=8,
            autofocus=True
        )
        submit_btn = gr.Button("发送", variant="primary", scale=1)

    with gr.Row():
        clear_btn = gr.Button("清空对话")

    msg.submit(
        fn=gradio_chat,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot]
    )
    submit_btn.click(
        fn=gradio_chat,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot]
    )
    clear_btn.click(
        fn=lambda: ("", []),
        inputs=[],
        outputs=[msg, chatbot]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        inbrowser=True
    )