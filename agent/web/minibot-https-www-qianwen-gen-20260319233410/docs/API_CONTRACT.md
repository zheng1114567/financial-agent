# API Contract: `/api/v2/chat` (SSE)

> ✅ **Status**: Ready for frontend SSE integration  
> 📌 **Base URL**: `http://127.0.0.1:3000/api`  
> 🔐 **Auth**: None (MVP guest mode)  
> 🌐 **CORS**: Explicitly allows `http://localhost:3000` and `http://127.0.0.1:3000`

---

## 🔹 Endpoint
`POST /api/v2/chat`

### Request
- **Method**: `POST`
- **Content-Type**: `application/json`
- **Body Schema**:
  ```json
  {
    "messages": [
      { "role": "user", "content": "Explain quantum computing simply." }
    ],
    "model": "qwen-plus",
    "temperature": 0.7
  }
  ```
- **Notes**:
  - `messages` is required, must be non-empty array.
  - `model` defaults to `"qwen-plus"` if omitted.
  - `temperature` is optional (0.0–2.0), default `0.7`.

### Response
- **Status**: `200 OK`
- **Content-Type**: `text/event-stream`
- **Event Format**:
  - Each event line ends with `\n\n`.
  - Must include `event:` and `data:` prefixes.

| Event     | `data` Schema                          | Description |
|-----------|------------------------------------------|-------------|
| `message` | `{"delta":{"content":"..."},"finish_reason":null}` | Streaming token chunk |
| `done`    | `{"finish_reason":"stop"}`               | Final response, stream complete |
| `error`   | `{"error":"validation_failed","message":"..."}` | Terminal error (e.g., malformed JSON) |

✅ **Example Stream**:
```text
event: message
data: {"delta":{"content":"Quantum"},"finish_reason":null}

event: message
data: {"delta":{"content":" computing"},"finish_reason":null}

event: done
data: {"finish_reason":"stop"}
```

---

## 🔹 Error Handling

| Status | Event | `data` example | Meaning |
|--------|-------|----------------|---------|
| `400`  | `error` | `{"error":"validation_failed","message":"'messages' is required"}` | Invalid or missing fields |
| `429`  | `error` | `{"error":"rate_limit_exceeded","retry_after":60}` | Too many requests; retry after seconds |
| `500`  | `error` | `{"error":"internal_error","message":"upstream timeout"}` | Backend failure |

> ⚠️ Frontend should:
> - Reconnect on network failure (with exponential backoff)
> - Show user-friendly message on `error` events
> - Stop rendering on `done` or `error`

---

## 🔹 CORS Configuration (Backend Enforced)
```http
Access-Control-Allow-Origin: http://localhost:3000, http://127.0.0.1:3000
Access-Control-Allow-Headers: Content-Type
Access-Control-Allow-Methods: POST
```

✅ No credentials required → safe for local dev.

---
📄 Generated from `docs/openapi.yaml` — always source of truth.