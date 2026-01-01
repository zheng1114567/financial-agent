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

    # 调用核心 RAG 函数
    try:
        answer, new_chat_history_messages, _ = ask_question(
            question=message,
            chat_history_messages=chat_history_messages,
            chat_history_str=""  # 如果 query.py 不需要，可忽略
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


with gr.Blocks(title="专业金融顾问 RAG 系统") as demo:
    gr.Markdown("## 📊 专业金融顾问 RAG 系统")
    gr.Markdown("基于上市公司年报与基金数据的智能问答 · 输入 `q` 结束对话")

    chatbot = gr.Chatbot(
        label="对话记录",
        height=500
    )

    msg = gr.Textbox(
        label="你的问题",
        placeholder="例如：中国铁路通信信号股份有限公司注册地在哪？",
        lines=1
    )

    with gr.Row():
        submit_btn = gr.Button("发送", variant="primary")
        clear_btn = gr.Button("清空")

    # 事件绑定
    submit_event = msg.submit(
        fn=gradio_chat,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot],
        queue=False
    )
    submit_btn.click(
        fn=gradio_chat,
        inputs=[msg, chatbot],
        outputs=[msg, chatbot],
        queue=False
    )
    clear_btn.click(
        fn=lambda: (None, []),
        inputs=[],
        outputs=[msg, chatbot]
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        inbrowser=True
    )