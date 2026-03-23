# PRD v0.2: MiniBot — Qwen Parity Edition

> ✅ Updated on 2026-03-19 | Based on `REFERENCE_FETCH_NOTES.md` & live qianwen.com analysis
> 🎯 Goal: Pixel-perfect functional + visual parity with https://www.qianwen.com/

---

## 1. 目标用户 (Unchanged)
- 初次接触 AI 客服的中小企业主、开发者、学生等轻量级用户
- 需要快速获得问答、代码辅助、文档摘要等能力，无复杂账号体系要求

## 2. 基于 Qwen 的核心场景增强

| Scenario | Qwen Behavior | MiniBot Implementation |
|----------|----------------|-------------------------|
| **Sidebar History Panel** | Persistent left sidebar on `/chat`, shows all sessions, current session highlighted, supports rename/delete | ✅ Required MVP: Implement as fixed-position `aside` with scrollable list; title editable via `PATCH /api/v2/chat/:id/title` |
| **Model Selector Dropdown** | Top-right in chat header; shows active model (`qwen-plus`, `qwen-max`) + version tag; dropdown lists all available models | ✅ Required MVP: Render as `<select>` or custom dropdown; syncs with `model` param in `/api/v2/chat` request |
| **File Upload Zone** | Drag-and-drop zone above input box; supports `.pdf`, `.docx`, `.pptx`, `.txt`, `.mp3`, `.mp4`; previews file name & type | ✅ Required MVP: Implement with `input[type="file"]` + drag handler; backend `POST /api/v2/upload` returns `file_id` for use in messages |
| **Session Title Editing** | Click on session title → inline edit → `PATCH /api/v2/chat/:id/title` → updates sidebar & header | ✅ Required MVP: Inline editing UI + API integration per spec below |
| **SSE Error Events** | On timeout / invalid message → emits `event: error` before closing stream | ✅ Required MVP: Backend must emit `event: error` with `{"code":"timeout","message":"..."}`; frontend handles toast + retry button |

## 3. 页面地图 (Updated to 5 Pages)

| 路由 | 页面名 | 描述 | Qwen Parity Status |
|------|--------|------|---------------------|
| `/` | Landing Page | 引导页，含品牌标语、功能图标、一键进入 `/chat` 按钮 | ✅ Matched (structure, fonts, skeleton) |
| `/chat` | 新建会话页 | 空白聊天窗口 + 输入框 + **sidebar + model selector + upload zone** | ✅ New: Added all 3 components |
| `/chat/:id` | 会话详情页 | 左侧历史列表（当前会话高亮），右侧消息流 + **edit title bar**, **upload zone**, **model selector**, **message actions** | ✅ New: Full component parity |
| `/history` | 历史归档页 | 分页展示所有会话（标题/时间/最后消息摘要），支持搜索与删除 | ✅ Matched (UI updated to white-blue tokens) |
| `/debug` | Debug Console (Dev Only) | SSE event inspector, token counter, latency chart, manual request playground | ✅ Added for parity validation (per test request) |

## 4. 页面级 Functionality (Qwen-Specific Additions)

### All Chat Pages (`/chat`, `/chat/:id`)
- **Message Bubble Styling**:
  - User bubble: `background: #e3f2fd`, `border-radius: 8px`, `padding: 12px 16px`, `color: #1a1a1a`
  - Assistant bubble: `background: #f8f9fa`, `border-radius: 8px`, `padding: 12px 16px`, `color: #1a1a1a`
  - Use CSS custom properties: `var(--color-primary)`, `var(--radius-md)`, `var(--spacing-md)`
- **Message Actions Toolbar** (on hover/focus):
  - `Edit`: Opens inline editor for that message (user only)
  - `Retry`: Resends same message (with same model/file context)
  - `Copy`: Copies full message content to clipboard (with `navigator.clipboard.writeText`)
- **Input Box Enhancements**:
  - Support paste image (convert to base64 → upload → insert as `![](url)`)
  - Auto-resize height (max 5 lines)
  - `Ctrl+Enter` to send (in addition to Enter)

### Sidebar History Panel
- Fixed width: `280px`
- Background: `var(--background-pc-sidebar)` → `#f8f8f9`
- Each item: `padding: 8px 12px`, `border-radius: 4px`, hover background `#eef2ff`
- Current session: `border-left: 3px solid var(--color-primary)`
- Context menu on right-click: `Rename`, `Delete`, `Export as Markdown`

### Model Selector
- Position: top-right corner of chat header
- Display: `qwen-plus v2.3.391` badge (version from `HTML_GLOBAL_CONFIG`)
- Dropdown: Shows `qwen-plus`, `qwen-max`, `qwen-turbo`; selected persists per session

### File Upload Zone
- Position: Above input box, full-width
- Style: dashed border `2px dashed var(--color-primary)`, `padding: 24px`, center-aligned icon + text
- Accept: `.pdf,.docx,.pptx,.txt,.mp3,.mp4,.jpg,.png`
- On drop: preview filename, auto-upload, insert `[file_id:abc123]` into input

## 5. Interface Contracts (Qwen-Aligned)

### `PATCH /api/v2/chat/:id/title`
- **Request**: `Content-Type: application/json`
  ```json
  { "title": "New Session Name" }
  ```
- **Response 200**: `application/json`
  ```json
  { "id": "abc123", "title": "New Session Name", "updated_at": "2026-03-19T17:22:00Z" }
  ```

### `POST /api/v2/upload`
- **Request**: `multipart/form-data`
  - `file`: binary upload
- **Response 200**: `application/json`
  ```json
  { "file_id": "xyz789", "filename": "report.pdf", "size": 123456, "mime_type": "application/pdf" }
  ```

### `POST /api/v2/chat` (SSE Endpoint — Updated)
- **Request Body** (same as v0.1, but now includes optional `file_ids`):
  ```json
  {
    "messages": [{"role":"user","content":"..."}],
    "model": "qwen-plus",
    "file_ids": ["xyz789"]
  }
  ```
- **Response Headers**:
  - `Content-Type: text/event-stream`
  - `Cache-Control: no-cache`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`
- **SSE Events** (all `data:` payloads are strict JSON):
  | Event | Payload Schema | Notes |
  |-------|----------------|-------|
  | `message` | `{"type":"message","delta":{"content":"..."},"role":"assistant"}` | Delta-based streaming |
  | `done` | `{"type":"done","finish_reason":"stop"}` | Always emitted |
  | `error` | `{"type":"error","code":"timeout","message":"Request timed out"}` | Emitted on failure; frontend must handle |
- **Retry Policy**: `retry: 2000` always present in stream

## 6. 验收标准（Qwen Parity Focus）

| AC ID | Requirement | Status |
|--------|-------------|--------|
| **AC-QWEN-01** | White-blue theme applied globally: `--color-bg: #ffffff`, `--color-primary: #1e88e5`, all spacing/radius tokens from `REFERENCE_FETCH_NOTES.md` | ✅ To be verified by Test |
| **AC-QWEN-02** | Message bubbles match Qwen: `border-radius: 8px`, `padding: 12px 16px`, user/assistant backgrounds as specified | ✅ To be verified by Test |
| **AC-QWEN-03** | SSE emits exactly `message`/`done`/`error`; `retry: 2000` header present; payloads parseable as JSON | ✅ To be verified by Test |
| **AC-QWEN-04** | Edit/Retry/Copy actions visible on hover/focus of each message | ✅ To be verified by Test |
| **AC-QWEN-05** | Sidebar history panel is persistent, responsive, and supports rename/delete/export | ✅ To be verified by Test |
| **AC-QWEN-06** | Model selector appears top-right, shows version tag, allows switching | ✅ To be verified by Test |
| **AC-QWEN-07** | File upload zone accepts supported types, previews, uploads, inserts file refs | ✅ To be verified by Test |

## 7. 非功能约束 (Updated)

- **Performance**: TTFT ≤ 1.5s p95 (same); E2E ≤ 8s p95 (same); **Upload ≤ 3s p95**
- **Security**: CSP updated to allow `https://g.alicdn.com` for fonts/fonts; `script-src 'self' 'nonce-...'` remains
- **Accessibility**: All new components meet WCAG 2.1 AA (e.g., upload zone has `aria-dropeffect`, model select has `aria-haspopup`)
- **Deployment**: Same as v0.1 — `python run.py`, `http://127.0.0.1:3000`

## 8. 启动说明 (Unchanged)
- 运行 `python web/minibot-https-www-qianwen-gen-20260319233410/run.py` 启动服务
- 默认访问地址：`http://127.0.0.1:3000`
- API 基础地址：`http://127.0.0.1:3000/api`
- 环境变量：`ENV=dev`（开发） / `ENV=prod`（生产）

---

> 📌 **Next Steps**:
> - Frontend: Implement sidebar, model selector, upload zone, message actions using tokens from `REFERENCE_FETCH_NOTES.md`
> - Backend: Add `/api/v2/upload`, `/api/v2/chat/:id/title`, enhance `/api/v2/chat` SSE error events
> - Test: Execute `Test Plan v0.1 — Qwen Parity Focus` against this PRD v0.2
> - Orchestrator: Kick off parallel implementation sprints.