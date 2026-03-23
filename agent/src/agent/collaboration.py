from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from agent.src.agent.shared import AGENT_ROOT, DATA_ROOT


TaskStatus = Literal[
    "created",
    "in_progress",
    "blocked",
    "review_required",
    "approved",
    "failed",
    "done",
]

AgentRole = Literal[
    "orchestrator",
    "product_manager",
    "frontend",
    "backend",
    "test",
    "reviewer",
    "user",
]

VALID_TASK_STATUSES = {
    "created",
    "in_progress",
    "blocked",
    "review_required",
    "approved",
    "failed",
    "done",
}

STATUS_ALIASES = {
    "completed": "done",
}

VALID_AGENT_ROLES = {
    "orchestrator",
    "product_manager",
    "frontend",
    "backend",
    "test",
    "reviewer",
    "user",
}

# PRD 模板文件顶部的版本标记；升高此数字会在下次 ensure 时自动备份旧模板并写入新结构
PRD_TEMPLATE_VERSION = 4

_PRD_TEMPLATE_VERSION_PATTERN = re.compile(
    r"agent-prd-template-version:\s*(\d+)",
    re.IGNORECASE,
)


def _parse_prd_template_version(content: str) -> int | None:
    """从已存在的 PRD_TEMPLATE.md 解析版本；无标记视为旧版 None（调用方可按 0 处理）。"""
    head = content[:4000] if content else ""
    m = _PRD_TEMPLATE_VERSION_PATTERN.search(head)
    return int(m.group(1)) if m else None


def _default_prd_template_markdown() -> str:
    """不含版本注释的 PRD 模板正文（与 PRD_TEMPLATE_VERSION 同步维护）。"""
    return (
        "# PRD 模板（含仿站与设计交付）\n\n"
        "> 说明：将本模板复制为同目录 `PRD.md` 并写满每一节，禁止保留「例：」「待补充」等占位句。\n"
        "> 工程师应能仅凭本文档实现前后端，无需再猜需求。若用户提供了参考网址，第 2、12、13、14 节为强制项。\n\n"
        "## 1. 产品目标\n"
        "- 背景与问题陈述（1～3 句）：\n"
        "- 目标用户画像（角色、技术水平、使用环境）：\n"
        "- 业务目标（可量化指标，如首屏时间、核心流程完成率）：\n"
        "- 成功定义（上线后如何判定「做对」）：\n\n"
        "## 2. 参考网址与仿站分析（有 URL 时必填）\n"
        "- 参考网址（完整 URL）：\n"
        "- 抓取记录：见 `REFERENCE_FETCH_NOTES.md`（须用工具写入摘要，禁止整站镜像与抄袭文案）\n"
        "- 信息架构（导航层级、页面类型、URL 猜测）：\n"
        "- 布局与版式（首屏分区、栅格/栏数、主内容区宽度、侧栏有无）：\n"
        "- 关键模块清单（Hero / 特性列表 / 表单 / 页脚 等）与视觉层级：\n"
        "- 交互习惯（滚动、Tab、弹窗、流式输出、分页、无限滚动）：\n"
        "- 不可复制项声明（品牌、原创文案、版权素材、商标）：\n\n"
        "## 3. 页面区块对照表（有 URL 时必填）\n"
        "| 参考站可见区块 | 本项目路由/页面 | 对应组件名 | 实现要点（含响应式） |\n"
        "| --- | --- | --- | --- |\n"
        "|  |  |  |  |\n\n"
        "## 4. 用户目标与范围收敛（MoSCoW）\n"
        "### Must（本期必须）\n"
        "- \n\n"
        "### Should（本期尽量）\n"
        "- \n\n"
        "### Could（后续迭代）\n"
        "- \n\n"
        "### Won't（明确不做及原因）\n"
        "- \n\n"
        "## 5. 功能对标矩阵（强制）\n"
        "| 能力/用户流程 | 用户是否需要 | 本期策略（完整/简化/不做） | 页面/组件 | 后端依赖（接口或纯前端） |\n"
        "| --- | --- | --- | --- | --- |\n"
        "|  |  |  |  |  |\n\n"
        "## 6. 用户故事与验收映射\n"
        "| ID | 用户故事（As a / I want / So that） | 前置条件 | 主流程步骤 | 期望结果 | 对应 API/页面 |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| US-01 |  |  |  |  |  |\n\n"
        "## 7. 页面地图\n"
        "- 页面清单（名称、路由 path、是否需登录）：\n"
        "- 导航关系（主导航、返回路径、深链）：\n"
        "- 首屏入口与关键 CTA：\n\n"
        "## 8. 功能需求（按页面，须可编码）\n"
        "### 8.1 页面：<名称>（路由：`/path`）\n"
        "- 主要组件树（父子关系）：\n"
        "- 功能点与用户可见行为：\n"
        "- 交互流程（步骤编号 1…n，含触发条件）：\n"
        "- 状态设计：加载中 / 空数据 / 错误 / 成功（各状态 UI 与文案要点）：\n"
        "- 调用的 API（方法+路径）与请求/响应字段（字段名、类型、必填、默认值）：\n"
        "- 边界与异常（超时、断网、403、429 等用户侧表现）：\n\n"
        "### 8.2 页面：<名称>（路由：`/path`）\n"
        "（复制上一节结构继续写）\n\n"
        "## 9. 数据模型与关键字段\n"
        "| 实体 | 说明 | 字段（名称/类型/约束） | 与 API 的对应关系 |\n"
        "| --- | --- | --- | --- |\n"
        "|  |  |  |  |\n\n"
        "## 10. API 契约草稿（须与矩阵中「本期实现」且非纯前端的每一行一一对应）\n"
        "### 10.1 `<METHOD> <path>` — <一句话用途>\n"
        "- 鉴权与请求头（如 `X-Client-ID`、`X-Session-ID`）：\n"
        "- Request JSON 示例（真实字段名）：\n"
        "- Response 200 JSON 示例：\n"
        "- 错误码：`400` / `401` / `429` / `503` 等各自含义与 body 结构：\n"
        "- SSE/流式（若有）：event 名、`data` 行 JSON 形状、结束事件：\n\n"
        "### 10.2 `<METHOD> <path>` — …\n"
        "（为每个接口复制一节）\n\n"
        "## 11. 非功能需求\n"
        "- 性能（首屏、TTFT、列表上限）：\n"
        "- 安全（CORS、敏感信息、速率限制）：\n"
        "- 可维护性（日志、配置、环境变量名）：\n"
        "- 兼容性（浏览器、移动端断点）：\n\n"
        "## 12. 验收标准（可执行检查清单）\n"
        "- [ ] 前端：逐页路由可访问、四态齐全、与 Design Tokens 一致\n"
        "- [ ] 后端：健康检查与契约内全部接口可调用\n"
        "- [ ] 联调：核心用户故事 US-01… 走通（写清具体点击路径）\n"
        "- [ ] 一键启动：`python run.py` 或文档等价命令可在干净环境跑通\n\n"
        "## 13. Design Tokens（前端必须可对齐）\n"
        "- 主色 / 辅色 / 背景 / 表面色 / 边框（给出 hex 或 CSS 变量名）：\n"
        "- 字体栈与字号阶梯（h1–h6、正文、小字、行高）：\n"
        "- 圆角、间距体系（如 4/8/12/16/24）、阴影层级：\n"
        "- 暗色或亮色主题说明：\n\n"
        "## 14. 启动说明（必须可直接运行，路径与 project_id 一致）\n"
        "- 网站根目录：`web/<project_id>/`\n"
        "- 一键启动：`python run.py` 或 `start.bat`\n"
        "- 前端目录：\n"
        "- 前端安装与启动命令：\n"
        "- 前端访问网址：\n"
        "- 后端目录：\n"
        "- 后端启动（PowerShell 须写 `.\\\\start-backend.bat` 或等价）：\n"
        "- API 基础地址与健康检查路径：\n"
        "- 环境变量（名称、是否必填、示例值）：\n"
    )


def _render_prd_template_file(version: int) -> str:
    return (
        f"<!-- agent-prd-template-version: {version} -->\n\n"
        f"{_default_prd_template_markdown()}"
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", text.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-_")
    return cleaned or "artifact"


def _should_write_fixed_prd(name: str, kind: str, author: str | None) -> bool:
    """
    仅当 PM 写入 PRD 类产物时，固定落盘为 docs/PRD.md。
    """
    text = f"{name} {kind}".lower()
    prd_keywords = ("prd", "product requirement", "产品需求", "產品需求", "需求文档", "需求文檔")
    is_prd_content = any(keyword in text for keyword in prd_keywords)
    if not is_prd_content:
        return False

    # author 为空时也落固定 PRD，避免 agent 忘记传 author 导致路径漂移。
    author_norm = (author or "").strip().lower()
    if not author_norm:
        return True
    return author_norm in {"product_manager", "pm", "产品经理", "產品經理"}


@dataclass
class TaskRecord:
    id: str
    project_id: str
    title: str
    description: str
    owner: str
    status: TaskStatus = "created"
    dependencies: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)


@dataclass
class ArtifactRecord:
    id: str
    project_id: str
    name: str
    kind: str
    path: str
    source_task_id: str | None = None
    author: str | None = None
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)


class CollaborationWorkspace:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or (Path(DATA_ROOT) / "collaboration"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _project_dir(self, project_id: str) -> Path:
        project_dir = self.base_dir / project_id
        (project_dir / "tasks").mkdir(parents=True, exist_ok=True)
        (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
        return project_dir

    def _project_web_dir(self, project_id: str) -> Path:
        web_dir = Path(AGENT_ROOT) / "web" / project_id
        web_dir.mkdir(parents=True, exist_ok=True)
        return web_dir

    def _project_docs_dir(self, project_id: str) -> Path:
        docs_dir = self._project_web_dir(project_id) / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        return docs_dir

    def ensure_prd_template(self, project_id: str) -> str:
        """
        在网站项目目录下确保固定 PRD 模板存在，并按版本自动升级。

        - 新文件：写入当前 PRD_TEMPLATE_VERSION。
        - 已存在且版本低于代码中的 PRD_TEMPLATE_VERSION：将旧内容备份到
          `PRD_TEMPLATE.v{旧版}-backup-{UTC时间}.md` 后覆盖为新模板。
        - 已存在且版本 >= PRD_TEMPLATE_VERSION：不修改（含用户手动调高版本的情况）。

        返回模板文件绝对路径。
        """
        docs_dir = self._project_docs_dir(project_id)
        template_path = docs_dir / "PRD_TEMPLATE.md"
        desired = _render_prd_template_file(PRD_TEMPLATE_VERSION)

        if not template_path.exists():
            template_path.write_text(desired, encoding="utf-8")
            return str(template_path)

        try:
            existing = template_path.read_text(encoding="utf-8")
        except OSError:
            template_path.write_text(desired, encoding="utf-8")
            return str(template_path)

        parsed = _parse_prd_template_version(existing)
        stored = 0 if parsed is None else parsed

        if stored >= PRD_TEMPLATE_VERSION:
            return str(template_path)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_name = f"PRD_TEMPLATE.v{stored}-backup-{ts}.md"
        backup_path = docs_dir / backup_name
        try:
            backup_path.write_text(existing, encoding="utf-8")
        except OSError:
            # 备份失败仍尝试升级，避免永久卡在旧模板
            pass

        template_path.write_text(desired, encoding="utf-8")
        return str(template_path)

    def create_task(
        self,
        project_id: str,
        title: str,
        description: str,
        owner: str,
        dependencies: list[str] | None = None,
    ) -> TaskRecord:
        if owner not in VALID_AGENT_ROLES:
            raise ValueError(f"invalid owner: {owner}")
        # 每次创建任务时确保项目目录下有固定 PRD 模板。
        self.ensure_prd_template(project_id)
        task = TaskRecord(
            id=f"task-{uuid4().hex[:10]}",
            project_id=project_id,
            title=title.strip(),
            description=description.strip(),
            owner=owner,
            dependencies=dependencies or [],
        )
        self._write_json(
            self._project_dir(project_id) / "tasks" / f"{task.id}.json",
            asdict(task),
        )
        return task

    def list_tasks(
        self,
        project_id: str,
        *,
        task_id: str | None = None,
        owner: str | None = None,
        status: str | None = None,
    ) -> list[TaskRecord]:
        task_dir = self._project_dir(project_id) / "tasks"
        tasks: list[TaskRecord] = []
        for path in sorted(task_dir.glob("*.json")):
            payload = self._read_json(path)
            if not payload:
                continue
            task = TaskRecord(**payload)
            if task_id and task.id != task_id:
                continue
            if owner and task.owner != owner:
                continue
            if status and task.status != status:
                continue
            tasks.append(task)
        tasks.sort(key=lambda item: item.updated_at, reverse=True)
        return tasks

    def get_task(self, project_id: str, task_id: str) -> TaskRecord:
        path = self._project_dir(project_id) / "tasks" / f"{task_id}.json"
        payload = self._read_json(path)
        if not payload:
            raise FileNotFoundError(f"task not found: {task_id}")
        return TaskRecord(**payload)

    def update_task(
        self,
        project_id: str,
        task_id: str,
        *,
        status: str | None = None,
        note: str | None = None,
        artifact_id: str | None = None,
    ) -> TaskRecord:
        path = self._project_dir(project_id) / "tasks" / f"{task_id}.json"
        payload = self._read_json(path)
        if not payload:
            raise FileNotFoundError(f"task not found: {task_id}")
        task = TaskRecord(**payload)
        if status:
            status = STATUS_ALIASES.get(status, status)
            if status not in VALID_TASK_STATUSES:
                raise ValueError(f"invalid status: {status}")
            task.status = status  # type: ignore[assignment]
        if note and note.strip():
            task.notes.append(note.strip())
        if artifact_id and artifact_id not in task.artifact_ids:
            task.artifact_ids.append(artifact_id)
        task.updated_at = _utc_now()
        self._write_json(path, asdict(task))
        return task

    def write_artifact(
        self,
        project_id: str,
        name: str,
        kind: str,
        content: str,
        *,
        source_task_id: str | None = None,
        author: str | None = None,
    ) -> ArtifactRecord:
        artifact_id = f"artifact-{uuid4().hex[:10]}"
        artifact_dir = self._project_dir(project_id) / "artifacts"
        docs_dir = self._project_docs_dir(project_id)
        project_output_dir = docs_dir / "generated"
        project_output_dir.mkdir(parents=True, exist_ok=True)

        if _should_write_fixed_prd(name=name, kind=kind, author=author):
            content_path = docs_dir / "PRD.md"
        else:
            file_ext = (
                ".json"
                if kind.lower().endswith("json")
                else ".md"
                if "md" in kind.lower()
                else ".txt"
            )
            content_path = project_output_dir / f"{_slugify(name)}-{artifact_id}{file_ext}"
        content_path.write_text(content, encoding="utf-8")
        artifact = ArtifactRecord(
            id=artifact_id,
            project_id=project_id,
            name=name.strip(),
            kind=kind.strip() or "text",
            path=str(content_path),
            source_task_id=source_task_id or None,
            author=author or None,
        )
        self._write_json(
            artifact_dir / f"{artifact_id}.meta.json",
            asdict(artifact),
        )
        return artifact

    def read_artifact(self, project_id: str, name_or_id: str) -> tuple[ArtifactRecord, str]:
        artifact_dir = self._project_dir(project_id) / "artifacts"
        for meta_path in sorted(artifact_dir.glob("*.meta.json")):
            payload = self._read_json(meta_path)
            if not payload:
                continue
            artifact = ArtifactRecord(**payload)
            if artifact.id == name_or_id or artifact.name == name_or_id:
                content = Path(artifact.path).read_text(encoding="utf-8")
                return artifact, content
        raise FileNotFoundError(f"artifact not found: {name_or_id}")

    def list_artifacts(self, project_id: str) -> list[ArtifactRecord]:
        artifact_dir = self._project_dir(project_id) / "artifacts"
        artifacts: list[ArtifactRecord] = []
        for meta_path in sorted(artifact_dir.glob("*.meta.json")):
            payload = self._read_json(meta_path)
            if payload:
                artifacts.append(ArtifactRecord(**payload))
        artifacts.sort(key=lambda item: item.updated_at, reverse=True)
        return artifacts

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "AgentRole",
    "ArtifactRecord",
    "CollaborationWorkspace",
    "PRD_TEMPLATE_VERSION",
    "TaskRecord",
    "TaskStatus",
    "VALID_AGENT_ROLES",
    "VALID_TASK_STATUSES",
]
