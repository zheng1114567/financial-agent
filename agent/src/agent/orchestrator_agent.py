"""
Orchestrator Agent：以回合制协调多 specialist agent，通过 interaction thread 收敛任务。
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.src.agent.collaboration import CollaborationWorkspace
from agent.src.agent.frontend_agent import get_runtime as get_frontend_runtime
from agent.src.agent.message_bus import get_message_bus
from agent.src.agent.product_manager_agent import get_runtime as get_product_runtime
from agent.src.agent.project_context import (
    guess_project_id_from_text,
    resolve_project_context,
)
from agent.src.agent.shared import AGENT_ROOT, create_memory_agent
from agent.src.agent.backend_agent import get_runtime as get_backend_runtime
from agent.src.agent.test_agent import get_runtime as get_test_runtime


THREAD_OWNER = "orchestrator"
SPECIALIST_ORDER = ("product_manager", "frontend", "backend", "test")
URL_PATTERN = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)


def _pm_reference_url_mandate(project_id: str, reference_urls: list[str]) -> str:
    """用户含参考网址时，对产品经理的强制交付条款（简体，写入首轮 inbox）。"""
    if not reference_urls:
        return ""
    urls = ", ".join(reference_urls)
    return (
        f"【参考网址强制条款】用户提供了参考网址：{urls}。\n"
        "作为产品经理，你必须完成以下交付（不可省略）：\n"
        f"1）使用你可用的 fetch/read 类工具访问上述网址，整理页面结构线索（标题层级、主导航、首屏模块、主要 CTA、页脚等）。"
        f"将摘要写入 web/{project_id}/docs/REFERENCE_FETCH_NOTES.md（控制篇幅，禁止整站镜像与侵权复制原文）。\n"
        f"2）在 web/{project_id}/docs/PRD.md 中按 PRD 模板填满「参考网址与仿站分析」「页面区块对照表」「Design Tokens」；"
        "对照表需逐行说明：参考站可见区块 → 本项目页面/组件名 → 实现要点。\n"
        "3）Design Tokens 必须具体可落地（主色/辅色/背景/边框、字体与字号阶梯、圆角、间距、阴影），供前端直接写成 CSS 变量。\n"
        "4）声明禁止复制原站品牌、原创文案与受版权素材；仅模仿结构与视觉层级。\n"
        "5）若工具抓取失败，在 REFERENCE_FETCH_NOTES.md 记录原因，并基于用户文字描述补全可执行的仿站规格。\n"
        "6）REFERENCE_FETCH_NOTES.md 必须含「功能与交互线索」小节；PRD.md 必须含「功能对标矩阵」"
        "（参考能力→用户是否需要→本期策略→页面/组件→后端依赖），且与用户一句话目标对齐，禁止默认做全站功能。\n"
        "7）API 契约：矩阵中「本期实现」且非纯前端的每一行须在「API 契约草稿」中有对应接口描述。\n"
        "8）若无法从页面推断功能，须通过 interaction 向用户或 orchestrator 提出 3～5 个封闭式问题后再定稿，禁止空猜。\n"
    )


def _frontend_reference_ui_mandate(project_id: str, reference_urls: list[str]) -> str:
    if not reference_urls:
        return ""
    return (
        f"【仿站界面】用户要求参考网址风格。请阅读 web/{project_id}/docs/PRD.md 中的参考分析、区块对照表与 Design Tokens；"
        "实现时必须使用 CSS 变量统一主题，保证现代观感（留白、层次、hover/focus、响应式）。"
        f"若 PRD 未写全 token，请自拟并写入 web/{project_id}/docs/UI_NOTES.md 说明取舍。\n"
    )


def _test_reference_acceptance_mandate(project_id: str, reference_urls: list[str]) -> str:
    if not reference_urls:
        return ""
    return (
        f"【仿站验收】用户提供了参考网址。验收时须检查：web/{project_id}/docs/REFERENCE_FETCH_NOTES.md 是否存在且非空，"
        f"且含「功能与交互线索」；PRD.md 是否含「页面区块对照表」「功能对标矩阵」「Design Tokens」；"
        f"API 是否与矩阵中本期实现项有对应；前端主要页面是否在布局层级上与 PRD 描述一致（允许色值合理偏差，不可完全无关）。\n"
    )

workspace = CollaborationWorkspace()
message_bus = get_message_bus()


def _resolve_project_id(user_input: str) -> str | None:
    hint = guess_project_id_from_text(user_input)
    project = resolve_project_context(hint) if hint else None
    if project:
        return project.project_id
    if _should_force_new_project(user_input):
        return _build_generated_project_id(user_input)
    project = resolve_project_context(None)
    if project:
        return project.project_id
    return _build_generated_project_id(user_input)


def _build_generated_project_id(user_input: str) -> str:
    """
    无法唯一命中已有项目时，自动生成新的 project_id。
    避免把 web 目录中的历史产物当成模板而阻塞流程。
    """
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", (user_input or "").strip().lower()).strip("-")
    base = "website"
    if normalized:
        tokens = [token for token in normalized.split("-") if token]
        if tokens:
            base = "-".join(tokens[:4])[:40].strip("-") or "website"
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}-gen-{timestamp}"


def _should_force_new_project(user_input: str) -> bool:
    text = (user_input or "").lower()
    has_reference_url = bool(_extract_reference_urls(user_input))
    force_keywords = (
        "新建",
        "新项目",
        "new project",
        "new website",
        "重新生成",
        "从零",
        "从零",
        "模仿",
        "仿",
        "生成",
    )
    return has_reference_url or any(keyword in text for keyword in force_keywords)


def _create_interaction_tasks(project_id: str, user_input: str) -> dict[str, str]:
    role_titles = {
        "product_manager": "需求梳理与协作澄清",
        "frontend": "前端实现与交互协作",
        "backend": "后端实现与接口协作",
        "test": "测试验证与验收协作",
    }
    task_ids: dict[str, str] = {}
    for role in SPECIALIST_ORDER:
        task = workspace.create_task(
            project_id=project_id,
            title=role_titles[role],
            description=user_input,
            owner=role,
        )
        task_ids[role] = task.id
    return task_ids


def _create_interaction_thread(project_id: str, user_input: str):
    return message_bus.create_thread(
        project_id=project_id,
        title="多 agent 交互协作线程",
        goal=user_input,
        participants=[THREAD_OWNER, *SPECIALIST_ORDER],
        owner=THREAD_OWNER,
    )


def _seed_initial_user_messages(
    project_id: str,
    thread_id: str,
    user_input: str,
    task_ids: dict[str, str],
)-> dict[str, str]:
    prd_template_path = workspace.ensure_prd_template(project_id)
    reference_urls = _extract_reference_urls(user_input)
    reference_hint = (
        f"参考网址（可模仿结构与交互）：{', '.join(reference_urls)}\n"
        if reference_urls
        else ""
    )
    pm_extra = _pm_reference_url_mandate(project_id, reference_urls)
    fe_extra = _frontend_reference_ui_mandate(project_id, reference_urls)
    test_extra = _test_reference_acceptance_mandate(project_id, reference_urls)
    role_focus = {
        "product_manager": "请优先做需求澄清、范围收敛、PRD/API 契约草稿，并主动协调其他角色。",
        "frontend": "请优先评估前端页面、入口、交互与缺失信息，并主动向 PM / backend / test 协作。",
        "backend": "请优先评估 API、数据模型、实现缺口与风险，并主动向 PM / frontend / test 协作。",
        "test": "请优先评估验收标准、测试策略、关键风险与验证路径，并主动向其他角色追问缺口。",
    }
    role_extra = {
        "product_manager": pm_extra,
        "frontend": fe_extra,
        "backend": "",
        "test": test_extra,
    }
    role_to_content: dict[str, str] = {}
    for role in SPECIALIST_ORDER:
        content = (
            f"用户目标：{user_input}\n"
            f"{reference_hint}"
            f"{role_extra.get(role, '')}"
            f"固定 PRD 模板路径：{prd_template_path}\n"
            f"PM 最终 PRD 固定输出路径：{Path(prd_template_path).with_name('PRD.md')}\n"
            f"{role_focus[role]}\n"
            "所有生成文档必须写入网站项目目录（web/<project_id>/docs/）。\n"
            "本次交付目标是“一键生成可直接运行的网站”，最终必须提供可访问网址与一键启动说明（run.py / start.bat）。\n"
            "禁止只写文档：product_manager 须产出可编码级 PRD.md；frontend/backend 必须使用文件工具在 web/<project_id>/ 下写入或修改真实源码（src/、main.py、api/），不得仅用 write_shared_artifact 写说明代替实现。\n"
            "Windows/PowerShell 防呆：启动说明须写 .\\start-backend.bat；批处理内说明尽量 ASCII；"
            "前后端端口分 3000/8000；单文件含连字符时 uvicorn 勿滥用 reload=True；"
            "requirements 中 fastapi>=0.115.2,<1.0 以减少与 gradio 等冲突；SSE 须按 event/data 分行。\n"
            "这不是固定 PM -> frontend -> backend -> test 流水线。"
            "请通过 interaction thread 主动与其他 agent 协作。"
        )
        role_to_content[role] = content
        message_bus.send_message(
            project_id=project_id,
            thread_id=thread_id,
            from_agent="user",
            to_agent=role,
            message_type="request",
            subject="用户请求",
            content=content,
            related_task_id=task_ids[role],
        )

    return role_to_content


def _extract_reference_urls(text: str) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for match in URL_PATTERN.findall(text or ""):
        normalized = match.rstrip(".,;")
        if normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    return results


def _read_json(path: Path) -> dict | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _overwrite_minimal_one_click_scaffold(web_dir: Path) -> None:
    """
    为达成「一键生成可直接运行」，由 orchestrator 兜底覆盖写入一组最小可启动 scaffolding。
    这样即使专家 agent 在生成过程中失败或写入了有拼字错误的半成品，也不会影响最终可运行性。
    """

    # ----------------------------
    # Backend (FastAPI)
    # ----------------------------
    requirements_txt = dedent(
        """\
        fastapi>=0.115.2,<1.0
        uvicorn[standard]>=0.30.6
        python-dotenv>=1.0.1
        httpx>=0.27.0
        redis>=5.0.0
        """
    )

    api_init = "# api package\n"
    api_v2_init = "# api.v2 package\n"

    main_py = dedent(
        """\
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware

        from api.v2.chat import router as chat_router
        from api.v2.history import router as history_router

        app = FastAPI(title="Qwen Chat MVP", version="2.0")

        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.get("/health")
        def health():
            return {"status": "ok"}

        # 兼容一些 agent 可能使用的旧路径
        @app.get("/api/health")
        def api_health():
            return {"status": "ok"}

        # API v2
        app.include_router(chat_router, prefix="/api/v2")
        app.include_router(history_router, prefix="/api/v2")
        """
    )

    chat_py = dedent(
        """\
        import asyncio
        import json
        import time
        import uuid
        from datetime import datetime, timezone
        from typing import Any, AsyncGenerator, Dict, List, Optional

        from fastapi import APIRouter, Header, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse

        router = APIRouter(tags=["chat"])

        # In-memory store for one-click MVP.
        # If you later add Redis, you can replace these implementations transparently.
        SESSION_TTL_SECONDS = 24 * 3600
        _sessions: Dict[str, Dict[str, Any]] = {}  # session_id -> {created_at, messages}
        _active_streams: Dict[str, int] = {}  # client_id -> count
        _lock = asyncio.Lock()


        def _now_iso() -> str:
            return datetime.now(timezone.utc).isoformat(timespec="seconds")


        def _cleanup_expired(now: float) -> None:
            expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TTL_SECONDS]
            for sid in expired:
                _sessions.pop(sid, None)


        def _new_session_id() -> str:
            # Keep prefix required by PRD.
            # 8 hex chars is enough for MVP; adjust if you want stricter pattern.
            return f"sess_{uuid.uuid4().hex[:8]}"


        async def _rate_limit_enter(client_id: str) -> None:
            async with _lock:
                _cleanup_expired(time.time())
                current = _active_streams.get(client_id, 0)
                if current >= 3:
                    raise HTTPException(status_code=429, detail="Too many concurrent SSE connections")
                _active_streams[client_id] = current + 1


        async def _rate_limit_exit(client_id: str) -> None:
            async with _lock:
                current = _active_streams.get(client_id, 0)
                _active_streams[client_id] = max(0, current - 1)


        def _validate_body(body: Dict[str, Any]) -> Dict[str, Any]:
            messages = body.get("messages")
            if not isinstance(messages, list) or len(messages) == 0:
                raise HTTPException(status_code=400, detail="'messages' must be a non-empty array")
            if not isinstance(body.get("model"), str):
                raise HTTPException(status_code=400, detail="'model' is required and must be a string")
            if body.get("stream") is not True:
                raise HTTPException(status_code=400, detail="'stream' must be true")
            return body


        async def _mock_assistant_stream(
            *,
            session_id: str,
            user_messages: List[Dict[str, Any]],
        ) -> AsyncGenerator[str, None]:
            # A deterministic mock response for frontend integration.
            full = "Hello! I'm Qwen. How can I help you today?"
            deltas = ["Hello! I'm Qwen.", " How can I help you today?"]
            assistant_acc = ""
            msg_id = "msg_001"

            # TTFT is handled in endpoint before returning headers.
            for delta in deltas:
                assistant_acc += delta
                payload = {
                    "id": msg_id,
                    "role": "assistant",
                    "content": assistant_acc,
                    "delta": delta,
                    "timestamp": _now_iso(),
                }
                yield f"event: message\\ndata: {json.dumps(payload, ensure_ascii=False)}\\n\\n"
                await asyncio.sleep(0.15)

            # Persist assistant message for history / refresh.
            _sessions[session_id]["messages"].extend(
                user_messages
                + [{"role": "assistant", "content": assistant_acc}]
            )
            yield "event: done\\ndata: {}\\n\\n"


        @router.post("/chat")
        async def chat_stream(
            request: Request,
            x_client_id: str = Header(..., alias="X-Client-ID"),
            x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
        ):
            body = await request.json()
            _validate_body(body)

            now = time.time()
            _cleanup_expired(now)

            sid_body = body.get("session_id")
            if isinstance(sid_body, str):
                sid_body = sid_body.strip() or None
            else:
                sid_body = None

            newly_created = False
            if x_session_id:
                session_id = x_session_id
                s = _sessions.get(session_id)
                if not s:
                    raise HTTPException(status_code=400, detail="invalid_session")
            elif sid_body:
                session_id = sid_body
                s = _sessions.get(session_id)
                if not s:
                    raise HTTPException(status_code=400, detail="invalid_session")
            else:
                session_id = _new_session_id()
                newly_created = True
                _sessions[session_id] = {"created_at": now, "messages": []}

            user_messages = body["messages"]
            if not isinstance(user_messages, list):
                raise HTTPException(status_code=400, detail="messages must be list")

            # Rate limit concurrency for SSE.
            await _rate_limit_enter(x_client_id)

            trace_id = str(uuid.uuid4())
            start = time.perf_counter()

            try:
                # Simulate TTFT <= 1.5s.
                await asyncio.sleep(0.6)
                ttft_ms = int((time.perf_counter() - start) * 1000)

                async def gen():
                    try:
                        async for chunk in _mock_assistant_stream(session_id=session_id, user_messages=user_messages):
                            yield chunk
                    finally:
                        await _rate_limit_exit(x_client_id)

                headers = {
                    "X-Trace-ID": trace_id,
                    "X-Response-Time": str(ttft_ms),
                }
                if newly_created:
                    headers["X-Session-ID"] = session_id

                return StreamingResponse(
                    gen(),
                    media_type="text/event-stream",
                    headers=headers,
                )
            except Exception:
                await _rate_limit_exit(x_client_id)
                raise


        @router.get("/chat/debug")
        async def debug_endpoint(
            request: Request,
            mode: str = "fail-post",
            code: int = 503,
            x_client_id: str = Header(..., alias="X-Client-ID"),
        ):
            # 兼容前端/测试：返回一个可控的失败模式
            if mode == "fail-post":
                return JSONResponse(status_code=code, content={"detail": f"Simulated {code} failure"})

            if mode == "fail-stream":
                # Fail after the first chunk to trigger reconnect logic (stream disconnect).
                await _rate_limit_enter(x_client_id)
                trace_id = str(uuid.uuid4())
                start = time.perf_counter()
                await asyncio.sleep(0.6)
                ttft_ms = int((time.perf_counter() - start) * 1000)

                async def gen():
                    try:
                        payload = {
                            "id": "msg_001",
                            "role": "assistant",
                            "content": "Hello! I'm Qwen.",
                            "delta": "Hello! I'm Qwen.",
                            "timestamp": _now_iso(),
                        }
                        yield f"event: message\\ndata: {json.dumps(payload, ensure_ascii=False)}\\n\\n"
                        await asyncio.sleep(0.2)
                        # Abruptly abort the stream.
                        raise RuntimeError("Simulated stream disconnect")
                    finally:
                        await _rate_limit_exit(x_client_id)

                headers = {
                    "X-Trace-ID": trace_id,
                    "X-Response-Time": str(ttft_ms),
                }
                return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)

            raise HTTPException(status_code=400, detail="Unknown debug mode")
        """
    )

    history_py = dedent(
        """\
        import time
        from datetime import datetime, timezone
        from typing import Any, Dict, List

        from fastapi import APIRouter

        from api.v2.chat import _sessions, SESSION_TTL_SECONDS, _cleanup_expired

        router = APIRouter(tags=["history"])


        def _now_iso() -> str:
            return datetime.now(timezone.utc).isoformat(timespec="seconds")


        @router.get("/history")
        async def history():
            now = time.time()
            _cleanup_expired(now)

            results: List[Dict[str, Any]] = []
            for sid, s in _sessions.items():
                created_ts = s.get("created_at", now)
                messages = s.get("messages", [])
                last_preview = ""
                # Find last assistant content for a better preview.
                for m in reversed(messages):
                    if isinstance(m, dict) and m.get("role") == "assistant":
                        last_preview = (m.get("content") or "")[:80]
                        break
                created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat(timespec="seconds")
                results.append(
                    {
                        "session_id": sid,
                        "created_at": created_at,
                        "last_preview": last_preview,
                    }
                )

            # last 20, newest first
            results.sort(key=lambda x: x["created_at"], reverse=True)
            return {"sessions": results[:20]}
        """
    )

    # Write backend files
    _write_text(web_dir / "requirements.txt", requirements_txt)
    _write_text(web_dir / "main.py", main_py)
    _write_text(web_dir / "api" / "__init__.py", api_init)
    _write_text(web_dir / "api" / "v2" / "__init__.py", api_v2_init)
    _write_text(web_dir / "api" / "v2" / "chat.py", chat_py)
    _write_text(web_dir / "api" / "v2" / "history.py", history_py)

    # ----------------------------
    # Frontend (Vite + React)
    # ----------------------------
    package_json = dedent(
        """\
        {
          "name": "qwen-chat-mvp",
          "private": true,
          "version": "0.0.1",
          "type": "module",
          "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
          },
          "dependencies": {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "react-router-dom": "^6.26.2"
          },
          "devDependencies": {
            "@types/react": "^18.3.5",
            "@types/react-dom": "^18.3.0",
            "@vitejs/plugin-react": "^4.3.1",
            "typescript": "^5.6.3",
            "vite": "^5.4.2"
          }
        }
        """
    )

    vite_config = dedent(
        """\
        import { defineConfig } from "vite";
        import react from "@vitejs/plugin-react";

        export default defineConfig({
          plugins: [react()],
          server: {
            host: "127.0.0.1",
            port: 3000,
            strictPort: true,
            proxy: {
              "/api": {
                target: "http://127.0.0.1:8000",
                changeOrigin: true,
              },
            },
          },
        });
        """
    )

    index_html = dedent(
        """\
        <!doctype html>
        <html lang="zh-Hant">
          <head>
            <meta charset="UTF-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0" />
            <title>Qwen Chat MVP</title>
          </head>
          <body>
            <div id="root"></div>
            <script type="module" src="/src/main.tsx"></script>
          </body>
        </html>
        """
    )

    tsconfig = dedent(
        """\
        {
          "compilerOptions": {
            "target": "ES2022",
            "useDefineForClassFields": true,
            "lib": ["ES2022", "DOM", "DOM.Iterable"],
            "module": "ESNext",
            "skipLibCheck": true,
            "moduleResolution": "Bundler",
            "resolveJsonModule": true,
            "isolatedModules": true,
            "noEmit": true,
            "jsx": "react-jsx",
            "strict": true,
            "types": []
          },
          "include": ["src"]
        }
        """
    )

    styles_css = dedent(
        """\
        :root {
          color-scheme: dark;
        }
        body {
          margin: 0;
          font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
          background: #1e1e1e;
          color: #fff;
        }
        .app {
          max-width: 900px;
          margin: 0 auto;
          padding: 24px;
        }
        header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #333;
        }
        nav a {
          color: #9bd;
          text-decoration: none;
          margin-left: 14px;
        }
        .chat-container {
          display: flex;
          flex-direction: column;
          gap: 12px;
          margin-top: 20px;
          min-height: calc(100vh - 120px);
        }
        .message {
          max-width: 80%;
          padding: 12px 14px;
          border-radius: 10px;
          line-height: 1.45;
          white-space: pre-wrap;
        }
        .message.user {
          margin-left: auto;
          background: #2563eb;
        }
        .message.assistant {
          margin-right: auto;
          background: #f3f4f6;
          color: #111;
        }
        .typing-indicator {
          display: inline-flex;
          gap: 4px;
          margin: 4px 0 0 0;
          color: #a0a0a0;
        }
        .dot {
          width: 8px;
          height: 8px;
          background: #a0a0a0;
          border-radius: 50%;
          animation: typingBounce 1.4s infinite ease-in-out;
        }
        .dot:nth-child(2) { animation-delay: 0.2s; }
        .dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBounce {
          0%, 100% { transform: translateY(0); opacity: 0.7; }
          50% { transform: translateY(-4px); opacity: 1; }
        }
        .skeleton-bubble {
          width: 100%;
          height: 48px;
          border-radius: 10px;
          background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%);
          background-size: 200% 200%;
          animation: skeletonShimmer 1.5s ease-in-out infinite;
        }
        @keyframes skeletonShimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        .chat-input-area {
          position: fixed;
          bottom: 24px;
          left: 50%;
          transform: translateX(-50%);
          width: 90%;
          max-width: 900px;
        }
        .chat-input {
          width: 100%;
          padding: 14px 16px;
          border-radius: 10px;
          border: 1px solid #333;
          background: #2d2d2d;
          color: #fff;
          font-size: 16px;
          outline: none;
          resize: none;
          height: 56px;
        }
        #reconnect-btn {
          display: block;
          margin: 24px auto 0;
          padding: 12px 24px;
          background-color: #007bff;
          color: white;
          border: none;
          border-radius: 10px;
          font-size: 16px;
          font-weight: 600;
          cursor: pointer;
        }
        .toast {
          position: absolute;
          top: 1rem;
          right: 1rem;
          z-index: 1000;
          padding: 12px 16px;
          border-radius: 10px;
          background-color: #ff4757;
          color: white;
          font-weight: 600;
          box-shadow: 0 8px 18px rgba(0,0,0,0.35);
          display: flex;
          gap: 12px;
          align-items: center;
        }
        .toast button {
          background: rgba(255,255,255,0.15);
          border: none;
          color: white;
          padding: 6px 10px;
          border-radius: 8px;
          cursor: pointer;
        }
        .history-card {
          background: #2d2d2d;
          border: 1px solid #333;
          border-radius: 12px;
          padding: 16px;
          margin: 10px 0;
          cursor: pointer;
        }
        .history-card:hover { background: #343434; }
        .history-card .meta { color: #a0a0a0; font-size: 14px; margin-top: 6px; }
        """
    )

    main_tsx = dedent(
        """\
        import React, { useEffect, useMemo, useRef, useState } from "react";
        import ReactDOM from "react-dom/client";
        import { BrowserRouter, Link, Route, Routes, useNavigate, useParams } from "react-router-dom";

        import "./styles.css";

        type ChatMessage = { id: string; role: "user" | "assistant"; content: string; delta?: string; timestamp?: string };
        type HistorySession = { session_id: string; created_at: string; last_preview: string };

        const LS_CLIENT_ID = "client_id";
        const LS_SESSION_ID = "session_id";
        const LS_MESSAGES_PREFIX = "chat_messages_";

        function uuidv4(): string {
          // Prefer crypto.randomUUID in modern browsers.
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const c: any = globalThis.crypto;
          if (c && typeof c.randomUUID === "function") return c.randomUUID();
          // Fallback (not perfect randomness, but ok for MVP).
          return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (ch) => {
            const r = (Math.random() * 16) | 0;
            const v = ch === "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
          });
        }

        function getClientId(): string {
          const existing = localStorage.getItem(LS_CLIENT_ID);
          if (existing) return existing;
          const v = uuidv4();
          localStorage.setItem(LS_CLIENT_ID, v);
          return v;
        }

        function getSessionMessages(sessionId: string): ChatMessage[] {
          const raw = localStorage.getItem(LS_MESSAGES_PREFIX + sessionId);
          if (!raw) return [];
          try {
            return JSON.parse(raw) as ChatMessage[];
          } catch {
            return [];
          }
        }

        function setSessionMessages(sessionId: string, msgs: ChatMessage[]) {
          localStorage.setItem(LS_MESSAGES_PREFIX + sessionId, JSON.stringify(msgs));
        }

        function Toast({ message, onClose }: { message: string; onClose: () => void }) {
          return (
            <div className="toast" data-position="top-right" role="alert" aria-live="assertive">
              <div>{message}</div>
              <button onClick={onClose} aria-label="Close toast">×</button>
            </div>
          );
        }

        function TypingIndicator() {
          return (
            <div className="typing-indicator" role="status" aria-live="polite" aria-busy="true">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </div>
          );
        }

        function SkeletonBubble() {
          return <div className="skeleton-bubble" role="status" aria-live="off" />;
        }

        function parseSseEvents(text: string): Array<{ event: string; data: any }> {
          const out: Array<{ event: string; data: any }> = [];
          const blocks = text.split(/\\n\\n/).map((b) => b.trim()).filter(Boolean);
          for (const block of blocks) {
            let eventName = "message";
            const dataLines: string[] = [];
            for (const line of block.split(/\\n/)) {
              const l = line.trim();
              if (!l) continue;
              if (l.startsWith("event:")) eventName = l.slice(6).trim();
              else if (l.startsWith("data:")) dataLines.push(l.slice(5).trim());
            }
            const dataStr = dataLines.join("\\n");
            let data: any = null;
            try {
              data = dataStr ? JSON.parse(dataStr) : {};
            } catch {
              data = dataStr;
            }
            out.push({ event: eventName, data });
          }
          return out;
        }

        async function streamChat(
          payload: any,
          clientId: string,
          onEvent: (ev: { event: string; data: any }) => void,
          signal: { cancelled: boolean },
        ) {
          const resp = await fetch("/api/v2/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Client-ID": clientId },
            body: JSON.stringify(payload),
          });

          // Read X-Session-ID early (needed by PRD).
          const respSessionId = resp.headers.get("X-Session-ID");
          if (!resp.ok) {
            const txt = await resp.text().catch(() => "");
            throw new Error(`POST failed: ${resp.status} ${txt || resp.statusText}`);
          }

          if (respSessionId) {
            // Let the caller react (redirect) if it wants.
            onEvent({ event: "session", data: { session_id: respSessionId } });
          }

          if (!resp.body) throw new Error("No response body");
          const reader = resp.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let buffer = "";
          let done = false;

          while (!done && !signal.cancelled) {
            const r = await reader.read();
            if (r.done) break;
            buffer += decoder.decode(r.value, { stream: true });

            // Parse full SSE chunks separated by blank line.
            const parts = buffer.split(/\\n\\n/);
            const complete = parts.slice(0, -1).join("\\n\\n");
            buffer = parts[parts.length - 1];
            if (complete.trim()) {
              const events = parseSseEvents(complete);
              for (const ev of events) onEvent(ev);
              if (events.some((e) => e.event === "done")) done = true;
            }
          }

          // If stream ended without explicit done, treat it as disconnect for reconnect UX.
          return;
        }

        function ChatPage({ mode }: { mode: "new" | "existing" }) {
          const navigate = useNavigate();
          const params = useParams();

          const initialSessionId = useMemo(() => {
            if (mode === "existing") return params.id as string;
            return localStorage.getItem(LS_SESSION_ID) || "";
          }, [mode, params.id]);

          const [sessionId, setSessionId] = useState<string>(initialSessionId);
          const [messages, setMessages] = useState<ChatMessage[]>(() => (initialSessionId ? getSessionMessages(initialSessionId) : []));
          const [draft, setDraft] = useState<string>("");

          const [toast, setToast] = useState<string>("");
          const [showSkeleton, setShowSkeleton] = useState<boolean>(false);
          const [typing, setTyping] = useState<boolean>(false);

          const [reconnectVisible, setReconnectVisible] = useState<boolean>(false);
          const retryTimerRef = useRef<number | null>(null);
          const streamSignalRef = useRef({ cancelled: false });

          const lastPayloadRef = useRef<any>(null);
          const attemptRef = useRef<number>(0);

          useEffect(() => {
            if (!sessionId) return;
            setSessionMessages(sessionId, messages);
          }, [sessionId, messages]);

          useEffect(() => {
            if (mode === "existing" && sessionId) {
              // Keep URL session id consistent with localStorage.
              localStorage.setItem(LS_SESSION_ID, sessionId);
              setMessages(getSessionMessages(sessionId));
            }
          }, [mode, sessionId]);

          const appendMessage = (msg: ChatMessage) => {
            setMessages((prev) => {
              const idx = prev.findIndex((m) => m.id === msg.id);
              if (idx >= 0) {
                const copy = prev.slice();
                copy[idx] = { ...copy[idx], ...msg };
                return copy;
              }
              return [...prev, msg];
            });
          };

          const showReconnect = () => {
            setReconnectVisible(true);
            setTyping(false);
            setShowSkeleton(false);
          };

          const retryWithBackoff = async () => {
            if (!lastPayloadRef.current) return;
            attemptRef.current += 1;
            const nextAttempt = attemptRef.current;

            // reset UI
            setReconnectVisible(false);
            setToast("");
            setTyping(true);
            setShowSkeleton(true);

            const clientId = getClientId();
            const signal = streamSignalRef.current;
            signal.cancelled = false;

            try {
              await streamChat(
                lastPayloadRef.current,
                clientId,
                (ev) => {
                  if (ev.event === "session") {
                    const newId = ev.data.session_id as string;
                    setSessionId(newId);
                    localStorage.setItem(LS_SESSION_ID, newId);
                    navigate(`/chat/${newId}`, { replace: true });
                    return;
                  }
                  if (ev.event === "message") {
                    const d = ev.data || {};
                    if (!d.delta && !d.content) return;
                    // First chunk -> hide skeleton.
                    setShowSkeleton(false);
                    setTyping(true);
                    appendMessage({
                      id: String(d.id || "msg_001"),
                      role: "assistant",
                      content: String(d.content || ""),
                      delta: String(d.delta || ""),
                      timestamp: String(d.timestamp || ""),
                    });
                  }
                  if (ev.event === "done") {
                    setTyping(false);
                    setShowSkeleton(false);
                  }
                  if (ev.event === "error") {
                    setToast(String(ev.data?.message || "LLM error"));
                    setTyping(false);
                    setShowSkeleton(false);
                  }
                },
                signal,
              );

              // If ended without done, treat as disconnect and reconnect.
              if (nextAttempt <= 3) {
                // The mock backend always sends done, but debug may disconnect.
                // We'll decide based on reconnect strategy elsewhere.
              }
            } catch (e: any) {
              if (nextAttempt <= 3) {
                retryTimerRef.current = window.setTimeout(() => retryWithBackoff(), 3000);
              } else {
                showReconnect();
              }
            }
          };

          const startChat = async () => {
            const clientId = getClientId();
            const trimmed = draft.trim();
            if (!trimmed) return;
            setDraft("");

            const userMessages = [{ role: "user", content: trimmed }];
            // Keep the payload stable for retries.
            const payload: any = {
              messages: [...userMessages],
              model: "qwen-plus",
              stream: true,
            };

            if (mode === "existing" && sessionId) {
              payload.session_id = sessionId;
            }
            // In /chat (new), session_id is intentionally omitted so backend generates it.

            lastPayloadRef.current = payload;
            attemptRef.current = 0;

            setToast("");
            setReconnectVisible(false);
            setTyping(true);
            setShowSkeleton(true);

            // Optimistically show user message.
            setMessages((prev) => [...prev, { id: `user_${Date.now()}`, role: "user", content: trimmed }]);

            const signal = streamSignalRef.current;
            signal.cancelled = false;

            try {
              await streamChat(
                payload,
                clientId,
                (ev) => {
                  if (ev.event === "session") {
                    const newId = ev.data.session_id as string;
                    setSessionId(newId);
                    localStorage.setItem(LS_SESSION_ID, newId);
                    navigate(`/chat/${newId}`, { replace: true });
                    return;
                  }
                  if (ev.event === "message") {
                    const d = ev.data || {};
                    setShowSkeleton(false);
                    appendMessage({
                      id: String(d.id || "msg_001"),
                      role: "assistant",
                      content: String(d.content || ""),
                      delta: String(d.delta || ""),
                      timestamp: String(d.timestamp || ""),
                    });
                    setTyping(true);
                  }
                  if (ev.event === "done") {
                    setTyping(false);
                    setShowSkeleton(false);
                  }
                  if (ev.event === "error") {
                    setToast(String(ev.data?.message || "LLM error"));
                    setTyping(false);
                    setShowSkeleton(false);
                  }
                },
                signal,
              );
            } catch (e: any) {
              // Initial POST failure UX: show reconnect button.
              setToast("Connection failed — click to retry");
              showReconnect();
            }
          };

          return (
            <div className="app">
              <header>
                <div style={{ fontWeight: 800 }}>Qwen Chat</div>
                <nav>
                  <Link to="/">Home</Link>
                  <Link to="/history">History</Link>
                </nav>
              </header>

              <div className="chat-container" aria-live="polite">
                {messages.map((m) => (
                  <div key={m.id} className={`message ${m.role}`}>
                    {m.content}
                  </div>
                ))}

                {showSkeleton ? <SkeletonBubble /> : null}
                {typing ? <TypingIndicator /> : null}

                {reconnectVisible ? (
                  <div style={{ textAlign: "center" }}>
                    <div style={{ color: "#ffd1d1", fontWeight: 700, marginBottom: 10 }}>
                      Connection failed — click to retry
                    </div>
                    <button id="reconnect-btn" onClick={retryWithBackoff}>
                      Reconnect
                    </button>
                  </div>
                ) : null}
              </div>

              <div className="chat-input-area">
                <textarea
                  className="chat-input"
                  placeholder="Message Qwen..."
                  rows={1}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      startChat();
                    }
                  }}
                />
              </div>

              {toast ? <Toast message={toast} onClose={() => setToast("")} /> : null}
            </div>
          );
        }

        function HistoryPage() {
          const [sessions, setSessions] = useState<HistorySession[]>([]);
          const [toast, setToast] = useState<string>("");
          const navigate = useNavigate();

          useEffect(() => {
            const run = async () => {
              try {
                const resp = await fetch("/api/v2/history");
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                setSessions((data?.sessions || []) as HistorySession[]);
              } catch {
                setToast("Failed to load history");
              }
            };
            run();
          }, []);

          return (
            <div className="app">
              <header>
                <div style={{ fontWeight: 800 }}>History</div>
                <nav>
                  <Link to="/">Home</Link>
                  <Link to="/chat">New Chat</Link>
                </nav>
              </header>

              {toast ? <Toast message={toast} onClose={() => setToast("")} /> : null}

              <div style={{ marginTop: 20 }}>
                {sessions.length === 0 ? <div style={{ color: "#a0a0a0" }}>No sessions yet</div> : null}
                {sessions.map((s) => (
                  <div
                    key={s.session_id}
                    className="history-card"
                    onClick={() => navigate(`/chat/${s.session_id}`)}
                    role="button"
                    tabIndex={0}
                  >
                    <div style={{ fontWeight: 800 }}>Session: {s.session_id}</div>
                    <div className="meta">{s.created_at}</div>
                    {s.last_preview ? <div className="meta" style={{ marginTop: 8 }}>{s.last_preview}</div> : null}
                  </div>
                ))}
              </div>
            </div>
          );
        }

        function HomePage() {
          return (
            <div className="app">
              <header>
                <div style={{ fontWeight: 800 }}>Qwen Chat</div>
                <nav>
                  <Link to="/history">History</Link>
                </nav>
              </header>
              <div style={{ marginTop: 60, textAlign: "center" }}>
                <h1 style={{ margin: 0 }}>Fast, lightweight, streaming chat</h1>
                <p style={{ color: "#a0a0a0" }}>Click below to start a new chat session.</p>
                <div style={{ marginTop: 20 }}>
                  <Link
                    to="/chat"
                    style={{
                      display: "inline-block",
                      padding: "12px 22px",
                      borderRadius: 12,
                      background: "#007bff",
                      color: "#fff",
                      textDecoration: "none",
                      fontWeight: 800,
                    }}
                  >
                    Start a New Chat
                  </Link>
                </div>
              </div>
            </div>
          );
        }

        function AppRoutes() {
          return (
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/chat" element={<ChatPage mode="new" />} />
              <Route path="/chat/:id" element={<ChatPage mode="existing" />} />
              <Route path="/history" element={<HistoryPage />} />
            </Routes>
          );
        }

        ReactDOM.createRoot(document.getElementById("root")!).render(
          <React.StrictMode>
            <BrowserRouter>
              <AppRoutes />
            </BrowserRouter>
          </React.StrictMode>,
        );
        """
    )

    src_dir = web_dir / "src"
    _write_text(web_dir / "package.json", package_json)
    _write_text(web_dir / "vite.config.ts", vite_config)
    _write_text(web_dir / "index.html", index_html)
    _write_text(web_dir / "tsconfig.json", tsconfig)
    _write_text(src_dir / "main.tsx", main_tsx)
    _write_text(src_dir / "styles.css", styles_css)

    # 一键启动脚本：一次运行即可启动前后端并输出可访问网址
    run_py = dedent(
        """\
        # -*- coding: utf-8 -*-
        \"\"\"One-shot start: backend 8000 + Vite 3000. Installs deps if missing.\"\"\"
        import os
        import subprocess
        import sys
        import time
        from pathlib import Path

        WEB_DIR = Path(__file__).resolve().parent
        os.chdir(WEB_DIR)

        def run_step(desc, args, *, shell=False, cwd=None):
            print(desc + "...")
            try:
                r = subprocess.run(
                    args,
                    cwd=cwd or str(WEB_DIR),
                    shell=shell,
                    check=False,
                )
                return r.returncode
            except FileNotFoundError as e:
                print("ERROR:", e)
                return 1

        def main():
            print("Starting site from", WEB_DIR)
            procs = []
            try:
                req = WEB_DIR / "requirements.txt"
                if req.exists():
                    run_step(
                        "pip install (backend deps)",
                        [sys.executable, "-m", "pip", "install", "-r", str(req)],
                    )

                if (WEB_DIR / "main.py").exists():
                    p = subprocess.Popen(
                        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                        cwd=str(WEB_DIR),
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
                    )
                    procs.append(("backend", p))
                    time.sleep(1.2)

                if (WEB_DIR / "package.json").exists():
                    nm = WEB_DIR / "node_modules"
                    if not nm.exists():
                        run_step("npm install", "npm install", shell=True)
                    p = subprocess.Popen(
                        "npm run dev",
                        cwd=str(WEB_DIR),
                        shell=True,
                    )
                    procs.append(("frontend", p))
                    time.sleep(2)

                print()
                print("=" * 50)
                print("  Open http://127.0.0.1:3000")
                print("  API    http://127.0.0.1:8000/health")
                print("=" * 50)
                print("Ctrl+C to stop")
                for name, proc in procs:
                    proc.wait()
            except KeyboardInterrupt:
                for name, proc in procs:
                    proc.terminate()
                print("\\nStopped.")

        if __name__ == "__main__":
            main()
        """
    )
    start_bat = (
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        "echo Starting...\r\n"
        "python run.py\r\n"
        "pause\r\n"
    )
    start_backend_bat = (
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        "echo Backend 8000...\r\n"
        "python -m uvicorn main:app --host 127.0.0.1 --port 8000\r\n"
        "pause\r\n"
    )
    local_dev_md = (
        f"# LOCAL_DEV\n\n"
        f"Website root: `{web_dir}`\n\n"
        "## One-shot\n"
        "- `python run.py` (installs pip deps if needed, starts backend then Vite)\n\n"
        "## Manual\n"
        "- Frontend: `npm install` then `npm run dev` -> http://127.0.0.1:3000\n"
        "- Backend: `.\\\\start-backend.bat` or "
        "`python -m uvicorn main:app --host 127.0.0.1 --port 8000`\n\n"
        "## Ports\n"
        "- UI: 3000\n"
        "- API: 8000\n"
    )
    _write_text(web_dir / "run.py", run_py)
    _write_text(web_dir / "start.bat", start_bat)
    _write_text(web_dir / "start-backend.bat", start_backend_bat)
    _write_text(web_dir / "docs" / "LOCAL_DEV.md", local_dev_md)


def _build_startup_guide(project_id: str) -> str:
    project = resolve_project_context(project_id)
    if not project or not project.web_dir:
        return "未定位到 web 项目目录，无法生成启动说明。"

    web_dir = Path(project.web_dir)
    has_run_py = (web_dir / "run.py").exists()
    has_package = (web_dir / "package.json").exists()
    has_backend = (web_dir / "main.py").exists()

    lines: list[str] = []
    if has_run_py and (has_package or has_backend):
        lines.extend([
            "【一键启动】生成可访问网址：",
            f"- 方式一：进入项目目录后执行 python run.py",
            f"- 方式二：双击 start.bat（Windows）",
            "- 启动后访问网址: http://127.0.0.1:3000",
            "",
            "启动说明（也可分两个终端手动执行）：",
        ])
    else:
        lines.append("启动说明（建议分两个终端执行）：")

    package_json = _read_json(web_dir / "package.json")
    if package_json and isinstance(package_json, dict):
        scripts = package_json.get("scripts")
        if isinstance(scripts, dict) and "dev" in scripts:
            lines.extend(
                [
                    f"- 前端目录: {web_dir}",
                    "- 前端安装依赖: npm install",
                    "- 前端启动命令: npm run dev",
                    "- 前端访问网址: http://127.0.0.1:3000",
                ]
            )

    if (web_dir / "main.py").exists():
        lines.extend(
            [
                f"- 后端目录: {web_dir}",
                (
                    f"- 后端启动命令: "
                    f'python -m uvicorn main:app --app-dir "{web_dir}" --host 127.0.0.1 --port 8000 --reload'
                ),
                "- 后端 API 基础地址: http://127.0.0.1:8000",
                "- 后端健康检查: http://127.0.0.1:8000/health",
            ]
        )

    if len(lines) == 1:
        lines.append("- 未检测到标准前后端启动入口，请让 frontend/backend agent 回写启动命令到共享产物。")
    return "\n".join(lines)


def _collect_new_artifacts(project_id: str, before_ids: set[str]) -> list:
    after_artifacts = workspace.list_artifacts(project_id)
    return [artifact for artifact in after_artifacts if artifact.id not in before_ids]


def _create_smoke_fallback_artifact(project_id: str, task_id: str, role: str, error_text: str) -> str:
    existing = workspace.list_artifacts(project_id)
    existing_names = [artifact.name for artifact in existing[:10]]
    role_to_name = {
        "frontend": "前端 smoke fallback 摘要",
        "backend": "后端 smoke fallback 摘要",
        "test": "测试 smoke fallback 摘要",
        "product_manager": "需求 smoke fallback 摘要",
    }
    content = (
        f"# {role} smoke fallback\n\n"
        f"- task_id: {task_id}\n"
        f"- role: {role}\n"
        f"- reason: {error_text}\n"
        f"- project_id: {project_id}\n"
        f"- existing_artifacts: {', '.join(existing_names) if existing_names else '无'}\n\n"
        "此产物由 orchestrator 在 smoke test 模式下自动生成，用于在模型异常时保留最小可验证轨迹。"
    )
    artifact = workspace.write_artifact(
        project_id=project_id,
        name=role_to_name.get(role, f"{role} smoke fallback 摘要"),
        kind=f"{role}_smoke_fallback",
        content=content,
        source_task_id=task_id,
        author=THREAD_OWNER,
    )
    workspace.update_task(project_id, task_id, artifact_id=artifact.id)
    return artifact.id


def _summarize_inbox(messages: list) -> str:
    if not messages:
        return "无"
    return "\n".join(
        f"- {message.id} | from={message.from_agent} | type={message.message_type} | subject={message.subject}"
        for message in messages
    )


def _inject_round_nudge(
    project_id: str,
    thread_id: str,
    task_ids: dict[str, str],
    round_index: int,
) -> None:
    """
    首轮种子消息处理完后 pending 常为 0，会导致工作流只跑一轮。
    在达到最小轮次前由 orchestrator 注入跟进消息，迫使各角色继续落地代码与联调。
    """
    web_abs = str(Path(AGENT_ROOT) / "web" / project_id)
    common = (
        f"（orchestrator 自动第 {round_index} 轮协作跟进）\n"
        f"- project_id: {project_id}\n"
        f"- 网站根目录（文件工具路径相对于仓库根，示例 web/{project_id}/...）：\n  {web_abs}\n\n"
    )
    nudges = {
        "product_manager": common
        + "请打开 docs/PRD.md：删除模板占位句，补全为可直接驱动开发的规格（逐页组件、逐接口字段、错误码、空状态、验收检查项）。"
        "若已有内容仍偏抽象，继续细化到工程师无需再猜。",
        "frontend": common
        + "必须使用文件工具修改 web/<project_id>/ 下真实前端工程（如 src/、样式、路由、package.json 若有变更须可安装）。"
        "在保留 run.py 与 package.json 可运行的前提下实现 PRD 的页面与交互；禁止只写共享产物说明而不改磁盘上的源码。",
        "backend": common
        + "必须使用文件工具修改 web/<project_id>/main.py、api/ 等真实后端代码，使接口与 PRD 一致且 uvicorn 可启动。"
        "禁止只写接口说明文档而不改实现。",
        "test": common
        + "根据 PRD 执行 request_http（如 /health）或 run_tests；将步骤、期望、实际工具输出片段写入共享产物。"
        "若服务未启动，明确 blocked 并指出需先执行 python run.py 或分终端启动。",
    }
    for role, content in nudges.items():
        message_bus.send_message(
            project_id=project_id,
            thread_id=thread_id,
            from_agent=THREAD_OWNER,
            to_agent=role,
            message_type="request",
            subject=f"协作跟进 R{round_index}",
            content=content,
            related_task_id=task_ids[role],
        )


def _build_turn_prompt(
    *,
    role: str,
    project_id: str,
    thread_id: str,
    task_id: str,
    user_input: str,
    inbox_messages: list,
    turn_index: int,
) -> str:
    web_abs = str(Path(AGENT_ROOT) / "web" / project_id)
    return (
        "你正在执行一轮多 agent interaction turn。\n"
        f"- project_id: {project_id}\n"
        f"- thread_id: {thread_id}\n"
        f"- role: {role}\n"
        f"- turn_index: {turn_index}\n"
        f"- related_task_id: {task_id}\n"
        f"- 网站根目录（实现代码与 docs 均在此；文件工具相对仓库根）：\n  {web_abs}\n"
        f"- 用户目标: {user_input}\n\n"
        "本轮 coordinator 观察到你的待处理消息：\n"
        f"{_summarize_inbox(inbox_messages)}\n\n"
        "你必须先调用 `read_agent_inbox(project_id, thread_id)` 与 `read_thread_messages(project_id, thread_id)`，"
        "再决定接下来要做什么。"
        "你可以写共享产物、更新共享任务，并用 `send_agent_message` 和其他 agent 协作。"
        "如果已有阶段结论、风险或阻塞，请主动给 orchestrator 发 `status`、`decision` 或 `blocker`。"
        "本轮开始前已存在的 inbox 消息会由 coordinator 在你执行结束后统一标记 processed，"
        "你不需要重复标记这些消息。"
        "至少执行一次工具调用；不要把自己当成固定流水线中的被动节点。"
        "一键交付要求：除文档外，必须在上述网站根目录内留下可运行的前后端代码增量（产品经理以 PRD.md 与契约为准）。"
    )


async def _run_specialist_turn(
    *,
    role: str,
    runtime,
    project_id: str,
    thread_id: str,
    task_id: str,
    user_input: str,
    inbox_messages: list,
    turn_index: int,
    allow_smoke_fallback: bool,
    timeout_seconds: int = 150,
) -> str:
    print(
        f"[orchestrator] turn start: role={role}, turn_index={turn_index}, inbox_messages={len(inbox_messages)}"
    )
    before_ids = {artifact.id for artifact in workspace.list_artifacts(project_id)}
    workspace.update_task(
        project_id,
        task_id,
        status="in_progress",
        note=f"{role} 第 {turn_index} 轮开始，待处理消息 {len(inbox_messages)} 条",
    )
    prompt = _build_turn_prompt(
        role=role,
        project_id=project_id,
        thread_id=thread_id,
        task_id=task_id,
        user_input=user_input,
        inbox_messages=inbox_messages,
        turn_index=turn_index,
    )
    try:
        result = await asyncio.wait_for(
            runtime.run_interaction_turn(
                prompt,
                interaction_thread_id=thread_id,
                stream_to_stdout=True,
            ),
            timeout=timeout_seconds,
        )
    except Exception as exc:
        print(f"[orchestrator] turn error: role={role}, turn_index={turn_index}, err={type(exc).__name__}: {exc}")
        new_artifacts = _collect_new_artifacts(project_id, before_ids)
        if new_artifacts:
            for artifact in new_artifacts:
                workspace.update_task(project_id, task_id, artifact_id=artifact.id)
            workspace.update_task(
                project_id,
                task_id,
                status="review_required",
                note=f"{role} 交互回合异常，但已留下 {len(new_artifacts)} 个产物：{type(exc).__name__}: {exc}",
            )
            return f"{role} 部分完成：{type(exc).__name__}: {exc}"
        if allow_smoke_fallback:
            artifact_id = _create_smoke_fallback_artifact(
                project_id,
                task_id,
                role,
                f"{type(exc).__name__}: {exc}",
            )
            workspace.update_task(
                project_id,
                task_id,
                status="review_required",
                note=f"{role} 触发 smoke fallback，产物 {artifact_id}",
            )
            return f"{role} 触发 smoke fallback：{type(exc).__name__}: {exc}"
        workspace.update_task(
            project_id,
            task_id,
            status="failed",
            note=f"{role} 执行失败：{type(exc).__name__}: {exc}",
        )
        return f"{role} 执行失败：{type(exc).__name__}: {exc}"

    new_artifacts = _collect_new_artifacts(project_id, before_ids)
    for artifact in new_artifacts:
        workspace.update_task(project_id, task_id, artifact_id=artifact.id)
    workspace.update_task(
        project_id,
        task_id,
        note=result[:400] if result else f"{role} 本轮未返回文本结果",
    )
    print(f"[orchestrator] turn end: role={role}, turn_index={turn_index}")
    return result


def _drain_orchestrator_inbox(project_id: str, thread_id: str) -> list:
    items = message_bus.inbox(
        project_id=project_id,
        recipient=THREAD_OWNER,
        thread_id=thread_id,
        only_pending=True,
    )
    for item in items:
        message_bus.mark_processed(project_id, item.id)
    return items


def _build_thread_summary(
    project_id: str,
    thread_id: str,
    *,
    rounds_executed: int,
    task_ids: dict[str, str],
    user_input: str,
) -> str:
    thread = message_bus.get_thread(project_id, thread_id)
    messages = message_bus.thread_messages(project_id, thread_id)
    artifacts = workspace.list_artifacts(project_id)
    artifact_summary = ", ".join(artifact.name for artifact in artifacts[:12]) or "无"
    task_statuses = []
    for role in SPECIALIST_ORDER:
        task_statuses.append(f"{role}={workspace.get_task(project_id, task_ids[role]).status}")
    reference_urls = _extract_reference_urls(user_input)
    startup_guide = _build_startup_guide(project_id)
    reference_summary = ", ".join(reference_urls) if reference_urls else "无"
    return (
        f"项目 `{project_id}` 的多 agent 交互已收敛。\n"
        f"- thread_id: {thread.id}\n"
        f"- thread_status: {thread.status}\n"
        f"- rounds_executed: {rounds_executed}\n"
        f"- message_count: {len(messages)}\n"
        f"- task_statuses: {', '.join(task_statuses)}\n"
        f"- artifact_summary: {artifact_summary}\n"
        f"- reference_urls: {reference_summary}\n"
        f"{startup_guide}"
    )


async def run_workflow(user_input: str) -> str:
    project_id = _resolve_project_id(user_input)

    # 新建 project_id 时 web 目录尚不存在，resolve_project_context 会失败；须先 ensure 再写入脚手架
    workspace.ensure_prd_template(project_id)
    web_root = Path(AGENT_ROOT) / "web" / project_id
    _overwrite_minimal_one_click_scaffold(web_root)

    is_smoke_test = "smoke test" in user_input.lower()
    task_ids = _create_interaction_tasks(project_id, user_input)
    thread = _create_interaction_thread(project_id, user_input)
    role_to_content = _seed_initial_user_messages(project_id, thread.id, user_input, task_ids)

    # 防呆：确保 frontend/backend 在开始时真的有 pending inbox
    # 如果因为某些原因 inbox 为空，会导致该角色不会被调度到执行回合。
    for role in SPECIALIST_ORDER:
        pending = message_bus.pending_count(project_id, thread_id=thread.id, recipient=role)
        print(f"[orchestrator] seed pending: role={role}, pending={pending}")
        if pending == 0:
            message_bus.send_message(
                project_id=project_id,
                thread_id=thread.id,
                from_agent="user",
                to_agent=role,
                message_type="request",
                subject="用户请求(补发)",
                content=role_to_content.get(role, ""),
                related_task_id=task_ids[role],
            )
            print(f"[orchestrator] seed pending was 0, re-sent: role={role}")

    runtimes = {
        "product_manager": get_product_runtime(),
        "frontend": get_frontend_runtime(),
        "backend": get_backend_runtime(),
        "test": get_test_runtime(),
    }

    max_rounds = 4 if is_smoke_test else 8
    min_full_rounds = 2 if is_smoke_test else 3
    rounds_executed = 0
    final_status = "resolved"

    for round_index in range(1, max_rounds + 1):
        rounds_executed = round_index
        progressed_this_round = False
        for role in SPECIALIST_ORDER:
            inbox_messages = message_bus.inbox(
                project_id=project_id,
                recipient=role,
                thread_id=thread.id,
                only_pending=True,
            )
            if not inbox_messages:
                continue

            progressed_this_round = True
            await _run_specialist_turn(
                role=role,
                runtime=runtimes[role],
                project_id=project_id,
                thread_id=thread.id,
                task_id=task_ids[role],
                user_input=user_input,
                inbox_messages=inbox_messages,
                turn_index=round_index,
                allow_smoke_fallback=is_smoke_test,
            )
            for message in inbox_messages:
                message_bus.mark_processed(project_id, message.id)

        _drain_orchestrator_inbox(project_id, thread.id)
        pending_messages = message_bus.pending_count(project_id, thread_id=thread.id)
        if pending_messages == 0:
            if round_index < min_full_rounds:
                _inject_round_nudge(project_id, thread.id, task_ids, round_index + 1)
                continue
            final_status = "resolved"
            break
        if not progressed_this_round:
            final_status = "blocked"
            break
    else:
        final_status = "resolved" if message_bus.pending_count(project_id, thread_id=thread.id) == 0 else "blocked"

    message_bus.update_thread_status(project_id, thread.id, final_status)
    summary = _build_thread_summary(
        project_id,
        thread.id,
        rounds_executed=rounds_executed,
        task_ids=task_ids,
        user_input=user_input,
    )
    message_bus.update_thread_status(project_id, thread.id, final_status, summary=summary)
    return summary


async def run_agent():
    memory_agent = create_memory_agent("memory_store_orchestrator.jsonl")
    print("🎛️ Orchestrator Agent 已启动（输入 'exit' 或按 Ctrl+C 退出）")

    while True:
        try:
            user_input = input("\n用户：")
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input or not user_input.strip():
            continue
        if user_input.lower().strip() == "exit":
            break

        print("-" * 50)
        final_answer = await run_workflow(user_input)
        print(final_answer)
        await asyncio.to_thread(
            memory_agent.process_interaction,
            user_input=user_input,
            agent_output=final_answer,
            source="orchestrator_agent",
        )
        await asyncio.to_thread(memory_agent.maintenance_tick)
        print("-" * 50)


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback

        traceback.print_exc()
