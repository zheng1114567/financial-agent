# 天气查询网站 PRD（仿 MSN 成都页）

> ✅ 项目 ID: `https-www-msn-cn-gen-20260320040024`  
> ✅ 交付目标：一键生成可直接运行的网站（前端 Vite + 后端 FastAPI）  
> ✅ 风格约束：白蓝配色（主色 `#1e88e5`），无障碍 AA+，CSP 兼容，TTFT ≤1.5s p95

---

## 一、目标用户与核心场景
- **目标用户**：中国境内需快速获取本地天气信息的普通网民（移动端优先）
- **核心场景**：用户打开网页即看到「成都市」当前天气与关键气象指标；支持摄氏/华氏切换；点击指标跳转详情地图页
- **用户目标一句话**：*“仿照 MSN 成都天气页，展示当前温度、体感、6 类气象指标卡片，支持单位切换”*

## 二、用户目标与范围收敛
| 类别 | 内容 |
|------|------|
| ✅ **Must Have（本期实现）** | 当前天气卡片（温度、体感、图标）、6 类气象指标卡片（空气质量/风/湿度/能见度/气压/露点）、℃/℉ 切换按钮、指标卡片点击跳转 `/maps/{id}/...`、`loc` 参数解码与 fallback（非法时回退至成都市） |
| ❌ **Won't Have（本期不做）** | 小时级预报滚动区、7 日预报列表、城市搜索框、多地点收藏、灾害预警弹窗、SSE 流式更新（本参考站为静态快照） |
| ⚠️ **Out of Scope（不负责）** | 地理编码服务（Nominatim 等）由 backend 调用；地图页 `/maps/...` 仅提供链接，不实现其内容 |

## 三、页面地图与信息架构
- 单页应用（SPA），入口：`/`
- URL 结构：`/?loc=BASE64_JSON&weadegreetype=C`（`weadegreetype` 默认 `C`，可为 `F`）
- 页面层级：
  - `HomePage`（根路由）
    - `CurrentWeatherCard`
    - `MetricCardList`（含 6 个 `MetricCard`）
    - `TempUnitToggle`
    - `LocationFallbackBanner`（仅当 `loc` 解析失败时显示）

## 四、参考网址与仿站分析
### 4.1 参考站信息架构（基于 REFERENCE_FETCH_NOTES.md）
- 首屏模块：城市标题 → 当前天气卡 → 气象指标卡片组（6 张横向排列）
- 无导航栏、无侧边栏、无页脚广告
- 所有指标卡片均含：图标 + 数值 + 单位 + 定义链接（`/maps/{id}/...`）

### 4.2 页面区块对照表
| 参考站可见区块 | 本项目页面/组件 | 实现要点 |
|----------------|------------------|-----------|
| 城市标题（四川省, 成都市） | `HomePage` 中 `location.name` 渲染 | 从 `loc` 解码 JSON 的 `c`（城市名）与 `r`（省份名）拼接，中文逗号分隔 |
| 当前天气卡片（温度、体感、天气图标） | `CurrentWeatherCard.tsx` | 温度字段：`current.temperature`, `current.feelsLike`；图标使用 SVG 内联或 CDN 图标；单位随 `weadegreetype` 切换 |
| 气象指标卡片组（6 类） | `MetricCardList.tsx` + `MetricCard.tsx`（循环渲染） | `metrics` 数组固定 6 项，`id` 必须为 `airquality`, `wind`, `humidity`, `visibility`, `pressure`, `dewpoint`；每张卡含 `value`, `unit`, `definitionUrl` 字段 |
| ℃/℉ 切换按钮 | `TempUnitToggle.tsx` | 控制 query 参数 `weadegreetype=C/F`，同步更新所有温度字段与单位 |
| 指标定义链接（ⓘ 或文字） | `MetricCard.tsx` 中 `<a href={metric.definitionUrl}>ⓘ</a>` | `definitionUrl` 为相对路径（如 `/maps/airquality/...`），前端直接 `window.open()` 或 `<a target="_blank">` |

### 4.3 Design Tokens（前端必须实现为 CSS 变量）
```css
:root {
  /* 色彩 */
  --color-primary: #1e88e5;       /* 主按钮、链接、图标 */
  --color-primary-hover: #1565c0;  /* 主按钮 hover */
  --color-bg: #ffffff;             /* 页面背景 */
  --color-surface: #f8f9fa;        /* 卡片背景 */
  --color-border: #e0e0e0;         /* 卡片边框、分割线 */
  --color-text-primary: #212121;    /* 主文本 */
  --color-text-secondary: #757575; /* 次要文本（单位、描述） */
  /* 字体与排版 */
  --font-family-base: "Segoe UI", system-ui, sans-serif;
  --font-size-xl: 2.5rem;          /* 当前温度 */
  --font-size-lg: 1.5rem;          /* 体感温度 */
  --font-size-md: 1rem;            /* 指标数值 */
  --font-size-sm: 0.875rem;         /* 单位、描述、链接 */
  /* 间距 */
  --space-xs: 0.25rem;             /* 图标与文字间隙 */
  --space-sm: 0.5rem;              /* 卡片内边距 */
  --space-md: 1rem;                /* 卡片间垂直间距 */
  --space-lg: 2rem;                /* 首屏模块间间距 */
  /* 圆角 */
  --radius-sm: 4px;                /* 卡片圆角 */
  --radius-md: 8px;                /* 按钮圆角 */
  /* 阴影 */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.1); /* 卡片阴影 */
}
```

## 五、功能对标矩阵（本期实现项）

| 参考能力（MSN 成都页） | 用户是否需要 | 本期策略 | 页面/组件 | 后端依赖 | 测试关注点 |
|------------------------|--------------|----------|------------|-----------|-------------|
| 当前天气卡片（温度、体感、天气图标、湿度、风速） | ✅ 是 | ✅ 实现 | `CurrentWeatherCard.tsx` | `GET /api/weather/forecast?loc=...` | 温度单位切换、图标映射、数值非空 |
| 7 天预报滚动列表（日期+白天/夜间温度+天气简述） | ❌ 否 | ❌ 不做 | — | — | 本项目不实现 |
| 温度单位切换按钮（℃/℉） | ✅ 是 | ✅ 实现 | `TempUnitToggle.tsx` | 前端状态 + query 参数透传 | 切换后所有温度字段实时刷新、URL query 同步更新 |
| 气象指标卡片组（空气质量、紫外线、能见度等共6类） | ✅ 是 | ✅ 实现 | `MetricCard.tsx`（循环渲染） | `GET /api/weather/forecast?loc=...` | `metrics[].id` 集合稳定、`definitionUrl` 可访问、图标正确 |
| 地理位置 fallback（loc 参数非法时显示默认城市） | ✅ 是 | ✅ 实现 | `LocationFallbackBanner.tsx` | `GET /api/weather/forecast?loc=invalid` → 400 + default loc | 响应 status=400、body 含 `default_location: {name: "成都市"}` |

> ⚠️ 注：backend 已草拟 `/api/weather/forecast` 接口，以下 4 项已确认：
> 1. `loc` fallback 策略：❌ **不支持纯文本**（如 `loc=四川成都`），**仅支持 Base64 编码的 JSON**（格式见下文）
> 2. `metrics.id` 集合：✅ **严格固定为 6 个 ID**（`airquality`, `wind`, `humidity`, `visibility`, `pressure`, `dewpoint`），禁止增删
> 3. `definitionUrl` 解析方式：✅ **相对路径**（如 `/maps/airquality/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=...`），前端直接拼接 `window.location.origin` 使用
> 4. 健康检查端点：✅ **添加 `/api/health`**（返回 `{"status": "ok", "timestamp": "ISO8601"}`）

## 六、API 契约草稿（后端必须实现）
### 6.1 `/api/health`（GET）
- **响应**：`200 OK`，JSON `{"status": "ok", "timestamp": "2026-03-19T20:12:34Z"}`

### 6.2 `/api/weather/forecast`（GET）
- **Query 参数**：
  - `loc`: **必需**，Base64 编码的 JSON 字符串，结构如下（MSNS 示例解码后）：
    ```json
    {
      "l": "四川省",
      "r": "成都市",
      "r2": "中国",
      "c": "成都市",
      "i": "CN",
      "g": "zh-cn",
      "x": "104.18299865722656",
      "y": "30.82200050354004"
    }
    ```
  - `weadegreetype`: 可选，`C`（摄氏，默认）或 `F`（华氏）
- **成功响应（200）**：
  ```json
  {
    "location": {
      "name": "成都市",
      "province": "四川省",
      "coordinates": {"lat": 30.822, "lng": 104.183}
    },
    "current": {
      "temperature": 22.5,
      "feelsLike": 24.1,
      "weatherIcon": "partly-cloudy-day",
      "humidity": 65,
      "windSpeed": 3.2,
      "windDirection": "N"
    },
    "metrics": [
      {
        "id": "airquality",
        "value": 62,
        "unit": "μg/m³",
        "definitionUrl": "/maps/airquality/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      },
      {
        "id": "wind",
        "value": 3,
        "unit": "km/h",
        "definitionUrl": "/maps/wind/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      },
      {
        "id": "humidity",
        "value": 65,
        "unit": "%",
        "definitionUrl": "/maps/humidity/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      },
      {
        "id": "visibility",
        "value": 22,
        "unit": "km",
        "definitionUrl": "/maps/visibility/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      },
      {
        "id": "pressure",
        "value": 1013.25,
        "unit": "mb",
        "definitionUrl": "/maps/pressure/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      },
      {
        "id": "dewpoint",
        "value": 15.2,
        "unit": "°C",
        "definitionUrl": "/maps/dewpoint/in-%E5%9B%9B%E5%B7%9D%E7%9C%81,%E6%88%90%E9%83%BD%E5%B8%82?loc=..."
      }
    ]
  }
  ```
- **错误响应（400 Bad Request）**：
  ```json
  {
    "error": "Invalid loc parameter",
    "default_location": {
      "name": "成都市",
      "province": "四川省"
    }
  }
  ```

## 七、验收标准（必须全部通过）
| 类别 | 标准 | 验证方式 |
|------|------|-----------|
| ✅ 功能 | `loc` 解析准确率 ≥99%（对合法 Base64 JSON 返回正确坐标；非法输入返回 400 + 成都市 fallback） | backend 单元测试 + test 发起 100 次随机 loc 请求 |
| ✅ 性能 | 首屏加载 ≤2s（Vite dev server 下，网络模拟 3G） | Lighthouse 报告 + Cypress `cy.visit().then(performance.timing)` |
| ✅ 交互 | 点击任意 `MetricCard`，新窗口打开对应 `/maps/{id}/...` URL（`window.open(..., '_blank')`） | Cypress E2E `.click()` + `cy.window().its('open').should('be.called')` |
| ✅ 错误态 | 输入 `/?loc=invalid`，页面显示 `LocationFallbackBanner`，文案为「无法定位城市，显示成都市天气」 | Cypress E2E 访问非法 URL 并断言 banner 文本 |
| ✅ 无障碍 | 所有图标均有 `aria-label`（如 `aria-label="空气质量：中等 (51-100)"`），所有卡片有语义化 heading | axe-core 扫描 + 手动 NVDA 验证 |

## 八、启动说明（Windows PowerShell）
1. **安装依赖**（首次运行）：
   ```powershell
   cd web\https-www-msn-cn-gen-20260320040024
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. **启动后端**（新终端）：
   ```powershell
   cd web\https-www-msn-cn-gen-20260320040024
   .\start-backend.bat
   ```
   > ✅ `start-backend.bat` 内容：`start "Backend" powershell -Command "python -m uvicorn main:app --host 127.0.0.1 --port 8000"`
3. **启动前端**（新终端）：
   ```powershell
   cd web\https-www-msn-cn-gen-20260320040024
   npm run dev
   ```
4. **访问网站**：
   - 前端地址：http://127.0.0.1:3000
   - 后端 API：http://127.0.0.1:8000/api/health（健康检查）
   - 示例请求：http://127.0.0.1:3000/?loc=eyJsIjoi5paw6YO95Yy6IiwiciI6IuWbm%2BW3neecgSIsInIyIjoi5oiQ6YO95biCIiwiYyI6IuS4reWNjuS6uuawkeWFseWSjOWbvSIsImkiOiJDTiIsImciOiJ6aC1jbiIsIngiOiIxMDQuMTgyOTk4NjU3MjI2NTYiLCJ5IjoiMzAuODIyMDAwNTAzNTQwMDQifQ%3D%3D&weadegreetype=C

> ⚠️ 注意：`start-backend.bat` 必须使用 `Start-Process` 后台启动，不可用管道阻塞（如 `python xxx.py 2>&1 | Out-File`）

---
✅ PRD 完成。已同步写入共享产物。