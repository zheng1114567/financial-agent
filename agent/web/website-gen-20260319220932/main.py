# -*- coding: utf-8 -*-
"""website-gen 專案後端入口（FastAPI）。

注意：此專案僅為佔位 API，不含 MiniBot 的 /v2/chat 串流。
若瀏覽器 / Vite 代理打到本機 8000 卻出現 404，代表你開錯後端程式。
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="website-gen API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {
        "message": "website-gen 佔位後端已啟動（無聊天串流）",
        "docs": "/docs",
        "health": "/health",
        "minibot_backend_hint": (
            "若前端是 MiniBot：請關閉本進程，在 minibot-https-www-qianwen-gen-20260319233410 "
            "專案執行 start-backend.bat 或 python src\\lib\\backend-sse-server.py"
        ),
    }


@app.post("/v2/chat")
def v2_chat_not_implemented():
    """避免 MiniBot 前端誤連本專案時只有難懂的 404。"""
    raise HTTPException(
        status_code=503,
        detail=(
            "此進程是 website-gen 的 main.py，未實作 POST /v2/chat。"
            "請改啟動 MiniBot 後端：進入 minibot-https-www-qianwen-gen-20260319233410 目錄後執行 "
            "start-backend.bat（或 python src\\lib\\backend-sse-server.py），同樣佔用 127.0.0.1:8000。"
        ),
    )
