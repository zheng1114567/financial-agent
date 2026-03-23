# 本地開發（避免 Agent / 手動啟動踩坑）

## 常見錯誤：`10061 目標計算機積極拒絕`

代表 **後端沒在聽** 或 **連錯埠**。請確認：

1. **專案資料夾名稱不要打錯**  
   正確示例：`minibot-https-www-qianwen-gen-20260319233410`  
   錯誤示例：`minibot-htttps-...`（多一個 `t`）→ 腳本路徑不存在，Python 不會起服務。

2. **後端埠為 `8000`**（不是 3000）  
   - 健康檢查：`http://127.0.0.1:8000/health`  
   - 聊天 SSE：`POST http://127.0.0.1:8000/v2/chat`（需頭 `X-Client-ID`）

3. **前端開發伺服器為 `3000`**（Vite）  
   - 頁面：`http://127.0.0.1:3000`  
   - 前端請求請用 **`/api/...`**，由 Vite 代理到 8000（見 `vite.config.ts`）。

## 建議啟動順序

**介面（網頁 UI）在 Vite `3000` 埠**，不是後端 `8000`。只開後端打開 8000 只會看到 API，沒有聊天頁面。

終端 A（專案根目錄）：

```bat
start-backend.bat
```

終端 B：

```bat
npm install
npm run dev
```

瀏覽器打開：**http://127.0.0.1:3000**

## 已接好的功能（本機記憶體）

- **新對話** `/chat`：串流顯示助手回覆；結束後跳轉 `/chat/{session_id}`。
- **繼續對話** `/chat/:id`：載入後端 session，可再送訊（帶 `session_id`）。
- **歷史** `/history`：`GET /v2/sessions`（依 `X-Client-ID` 篩選）。
- **改標題**：詳情頁點標題編輯 → `PATCH /v2/chat/:id/title`。

後端為示範用 **記憶體** 儲存，重啟 Python 後歷史會清空。

## 不要用錯誤方式啟動後端

- `python -m uvicorn src.lib.backend-sse-server:app` **無效**：模組名含連字號 `-`，不能這樣 import。  
- 請使用 **`start-backend.bat`** 或：`python src\lib\backend-sse-server.py`（工作目錄為專案根目錄）。
