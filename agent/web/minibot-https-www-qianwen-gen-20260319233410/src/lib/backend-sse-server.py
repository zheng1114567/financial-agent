import asyncio
import json
import time
from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware

app = FastAPI(title="MiniBot SSE Backend", version="0.2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# session_id -> { client_id, messages, title, updated_at }
SESSIONS: Dict[str, Dict[str, Any]] = {}


def gen_trace_id() -> str:
    return f"trace-{int(time.time() * 1000000)}-{uuid.uuid4().hex[:6]}"


def _first_user_title(messages: List[dict]) -> str:
    for m in messages or []:
        if isinstance(m, dict) and m.get("role") == "user":
            c = (m.get("content") or "").strip()
            if not c:
                continue
            return c[:48] + ("…" if len(c) > 48 else "")
    return "新對話"


def _ensure_session(client_id: str, session_id: Optional[str]) -> str:
    if session_id:
        sess = SESSIONS.get(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="session not found")
        if sess["client_id"] != client_id:
            raise HTTPException(status_code=403, detail="session belongs to another client")
        return session_id
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {
        "client_id": client_id,
        "messages": [],
        "title": "新對話",
        "updated_at": _now_iso(),
    }
    return sid


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


async def mock_stream_response(
    messages: list,
    model: str = "qwen-plus",
    file_ids: Optional[list] = None,
    text_holder: Optional[Dict[str, str]] = None,
):
    """流式輸出 SSE；同時把助手全文寫入 text_holder['text']。"""
    response_text = (
        "這是本地模擬回覆（未接真實大模型）。"
        "Quantum computing leverages quantum mechanics to process information using qubits, "
        "which can exist in superposition of 0 and 1 simultaneously."
    )
    words = response_text.split()

    await asyncio.sleep(0.15)

    for i, word in enumerate(words):
        sep = " " if i < len(words) - 1 else ""
        piece = word + sep
        if text_holder is not None:
            text_holder["text"] = text_holder.get("text", "") + piece
        delta = {"delta": {"content": piece}, "finish_reason": None}
        yield f"event: message\ndata: {json.dumps(delta, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.04)

    yield f'event: done\ndata: {json.dumps({"finish_reason": "stop"})}\n\n'


@app.post("/v2/chat")
async def chat_v2(request: Request):
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Client-ID header is required")

    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    messages = body.get("messages")
    model = body.get("model", "qwen-plus")
    file_ids = body.get("file_ids") or []
    session_id_in = body.get("session_id")

    if not messages or not isinstance(messages, list) or len(messages) == 0:
        raise HTTPException(
            status_code=400,
            detail="'messages' is required and must be a non-empty array",
        )

    allowed_models = ["qwen-plus", "qwen-max", "qwen-turbo"]
    if model not in allowed_models:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid model '{model}'. Allowed: {allowed_models}",
        )

    sid = _ensure_session(client_id, session_id_in)
    sess = SESSIONS[sid]
    # 正規化為簡單 dict
    norm: List[Dict[str, str]] = []
    for m in messages:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
            norm.append(
                {
                    "role": m["role"],
                    "content": str(m.get("content", "")),
                }
            )
    sess["messages"] = norm
    auto_title = _first_user_title(norm)
    if sess.get("title") in ("", "新對話") and auto_title != "新對話":
        sess["title"] = auto_title
    sess["updated_at"] = _now_iso()

    text_holder: Dict[str, str] = {"text": ""}

    async def event_stream():
        try:
            async for chunk in mock_stream_response(norm, model, file_ids, text_holder):
                yield chunk
        finally:
            reply = (text_holder.get("text") or "").strip()
            if reply:
                cur = sess.get("messages") or []
                # 避免重複追加同一段（重試時）
                if not cur or cur[-1].get("role") != "assistant" or cur[-1].get("content") != reply:
                    cur = list(cur)
                    cur.append({"role": "assistant", "content": reply})
                    sess["messages"] = cur
            sess["updated_at"] = _now_iso()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "X-Response-Time": str(int(time.time() * 1000)),
            "X-Trace-ID": gen_trace_id(),
            "X-Session-ID": sid,
            "X-Client-ID": client_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@app.get("/v2/sessions")
async def list_sessions(request: Request):
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Client-ID header is required")
    items = []
    for session_id, data in SESSIONS.items():
        if data["client_id"] != client_id:
            continue
        msgs: List[dict] = data.get("messages") or []
        preview = ""
        if msgs:
            last = msgs[-1]
            preview = (last.get("content") or "")[:160]
        items.append(
            {
                "session_id": session_id,
                "title": data.get("title") or "新對話",
                "updated_at": data.get("updated_at") or "",
                "last_preview": preview,
            }
        )
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"sessions": items}


@app.get("/v2/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Client-ID header is required")
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if sess["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    return {
        "session_id": session_id,
        "title": sess.get("title") or "新對話",
        "messages": sess.get("messages") or [],
        "updated_at": sess.get("updated_at") or "",
    }


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/v2/upload")
async def upload_file(request: Request):
    form = await request.form()
    file = form.get("file")
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    filename = file.filename
    raw = await file.read()
    size = len(raw)
    file_id = f"file_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    return {
        "file_id": file_id,
        "filename": filename,
        "size": size,
        "mime_type": getattr(file, "content_type", None) or "application/octet-stream",
    }


@app.patch("/v2/chat/{chat_id}/title")
async def update_chat_title(chat_id: str, request: Request):
    client_id = request.headers.get("X-Client-ID")
    if not client_id:
        raise HTTPException(status_code=400, detail="X-Client-ID header is required")
    sess = SESSIONS.get(chat_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if sess["client_id"] != client_id:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        body = await request.json()
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    title = body.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        raise HTTPException(
            status_code=400,
            detail="'title' is required and must be a non-empty string",
        )
    title = title.strip()[:128]
    sess["title"] = title
    sess["updated_at"] = _now_iso()
    return {
        "id": chat_id,
        "title": title,
        "updated_at": sess["updated_at"],
    }


if __name__ == "__main__":
    import uvicorn

    # reload=True 需 import 字串；檔名含連字號無法當模組，故關閉 reload 避免警告與異常
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
