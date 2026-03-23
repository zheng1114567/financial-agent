import json
from typing import List

from langchain_core.tools import tool

from agent.src.agent.collaboration import (
    CollaborationWorkspace,
    STATUS_ALIASES,
    VALID_AGENT_ROLES,
    VALID_TASK_STATUSES,
)
from agent.src.agent.project_context import (
    discover_projects,
    format_project_context_summary,
    resolve_project_context,
)


workspace = CollaborationWorkspace()


@tool("list_projects")
def list_projects() -> str:
    """列出当前仓库中可识别的项目。"""
    projects = discover_projects()
    if not projects:
        return "当前未发现任何项目目录。"
    return "\n\n".join(format_project_context_summary(project) for project in projects)


@tool("resolve_project_context")
def resolve_project_context_tool(project_hint: str = "") -> str:
    """根据项目名提示解析项目上下文；为空时若存在多个项目会返回无法唯一确定。"""
    project = resolve_project_context(project_hint or None)
    if not project:
        return "无法唯一解析项目，请先调用 list_projects 查看可用项目名。"
    return format_project_context_summary(project)


@tool("create_shared_task")
def create_shared_task(
    project_id: str,
    title: str,
    description: str,
    owner: str,
    dependencies_json: str = "[]",
) -> str:
    """在共享工作区中创建任务，owner 必须是 orchestrator/product_manager/frontend/backend/test/reviewer/user 之一。"""
    if owner not in VALID_AGENT_ROLES:
        return f"owner 无效，可选值：{', '.join(sorted(VALID_AGENT_ROLES))}"
    try:
        dependencies = json.loads(dependencies_json) if dependencies_json.strip() else []
        if not isinstance(dependencies, list):
            return "dependencies_json 必须是 JSON 数组。"
    except json.JSONDecodeError:
        return "dependencies_json 不是合法 JSON。"
    task = workspace.create_task(
        project_id=project_id,
        title=title,
        description=description,
        owner=owner,
        dependencies=[str(item) for item in dependencies],
    )
    return json.dumps(task.__dict__, ensure_ascii=False, indent=2)


@tool("list_shared_tasks")
def list_shared_tasks(
    project_id: str,
    task_id: str = "",
    owner: str = "",
    status: str = "",
) -> str:
    """列出共享工作区中的任务，可按 owner 或 status 过滤。"""
    if owner and owner not in VALID_AGENT_ROLES:
        return f"owner 无效，可选值：{', '.join(sorted(VALID_AGENT_ROLES))}"
    if status and status not in VALID_TASK_STATUSES:
        return f"status 无效，可选值：{', '.join(sorted(VALID_TASK_STATUSES))}"
    tasks = workspace.list_tasks(
        project_id,
        task_id=task_id or None,
        owner=owner or None,
        status=status or None,
    )
    if not tasks:
        return "当前没有匹配的任务。"
    return "\n\n".join(json.dumps(task.__dict__, ensure_ascii=False, indent=2) for task in tasks)


@tool("get_shared_task")
def get_shared_task(project_id: str, task_id: str) -> str:
    """读取单个共享任务。"""
    try:
        task = workspace.get_task(project_id, task_id)
    except Exception as exc:
        return f"读取任务失败: {exc}"
    return json.dumps(task.__dict__, ensure_ascii=False, indent=2)


@tool("update_shared_task")
def update_shared_task(
    project_id: str,
    task_id: str,
    status: str = "",
    note: str = "",
    artifact_id: str = "",
) -> str:
    """更新共享任务状态，并可附带备注或关联 artifact_id。"""
    if status:
        status = STATUS_ALIASES.get(status, status)
    if status and status not in VALID_TASK_STATUSES:
        return f"status 无效，可选值：{', '.join(sorted(VALID_TASK_STATUSES))}"
    try:
        task = workspace.update_task(
            project_id=project_id,
            task_id=task_id,
            status=status or None,
            note=note or None,
            artifact_id=artifact_id or None,
        )
    except Exception as exc:
        return f"更新任务失败: {exc}"
    return json.dumps(task.__dict__, ensure_ascii=False, indent=2)


@tool("write_shared_artifact")
def write_shared_artifact(
    project_id: str,
    name: str,
    kind: str,
    content: str,
    source_task_id: str = "",
    author: str = "",
) -> str:
    """写入共享产物，例如 prd 草稿、页面结构、接口契约、测试报告。"""
    try:
        artifact = workspace.write_artifact(
            project_id=project_id,
            name=name,
            kind=kind,
            content=content,
            source_task_id=source_task_id or None,
            author=author or None,
        )
    except Exception as exc:
        return f"写入产物失败: {exc}"
    return json.dumps(artifact.__dict__, ensure_ascii=False, indent=2)


@tool("read_shared_artifact")
def read_shared_artifact(project_id: str, name_or_id: str) -> str:
    """读取共享产物的元数据和内容。"""
    try:
        artifact, content = workspace.read_artifact(project_id, name_or_id)
    except Exception as exc:
        return f"读取产物失败: {exc}"
    payload = {"artifact": artifact.__dict__, "content": content}
    return json.dumps(payload, ensure_ascii=False, indent=2)


@tool("list_shared_artifacts")
def list_shared_artifacts(project_id: str) -> str:
    """列出某个项目已有的共享产物。"""
    artifacts = workspace.list_artifacts(project_id)
    if not artifacts:
        return "当前没有共享产物。"
    return "\n\n".join(json.dumps(artifact.__dict__, ensure_ascii=False, indent=2) for artifact in artifacts)


def get_collaboration_tools() -> List:
    return [
        list_projects,
        resolve_project_context_tool,
        create_shared_task,
        list_shared_tasks,
        get_shared_task,
        update_shared_task,
        write_shared_artifact,
        read_shared_artifact,
        list_shared_artifacts,
    ]


__all__ = ["get_collaboration_tools"]
