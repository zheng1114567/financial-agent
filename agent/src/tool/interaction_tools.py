from __future__ import annotations

import json
from dataclasses import asdict
from typing import List

from langchain_core.tools import tool

from agent.src.agent.interaction_protocol import VALID_MESSAGE_TYPES, VALID_THREAD_STATUSES
from agent.src.agent.message_bus import get_message_bus
from agent.src.agent.project_context import discover_projects


def _project_exists(project_id: str) -> bool:
    return any(project.project_id == project_id for project in discover_projects())


def _dump(payload) -> str:
    if isinstance(payload, list):
        return json.dumps([asdict(item) for item in payload], ensure_ascii=False, indent=2)
    return json.dumps(asdict(payload), ensure_ascii=False, indent=2)


def get_interaction_tools(agent_name: str) -> List:
    bus = get_message_bus()

    @tool("create_interaction_thread")
    def create_interaction_thread(
        project_id: str,
        title: str,
        goal: str,
        participants_json: str,
    ) -> str:
        """创建多 agent 对话线程。participants_json 必须是 JSON 数组。"""
        if not _project_exists(project_id):
            return f"项目不存在: {project_id}"
        try:
            participants = json.loads(participants_json)
        except json.JSONDecodeError:
            return "participants_json 不是合法 JSON。"
        if not isinstance(participants, list) or not participants:
            return "participants_json 必须是非空 JSON 数组。"

        try:
            thread = bus.create_thread(
                project_id=project_id,
                title=title,
                goal=goal,
                participants=[str(item) for item in participants],
                owner=agent_name,
            )
        except Exception as exc:
            return f"创建线程失败: {exc}"
        return _dump(thread)

    @tool("get_interaction_thread")
    def get_interaction_thread(project_id: str, thread_id: str) -> str:
        """读取对话线程。"""
        try:
            thread = bus.get_thread(project_id, thread_id)
        except Exception as exc:
            return f"读取线程失败: {exc}"
        return _dump(thread)

    @tool("send_agent_message")
    def send_agent_message(
        project_id: str,
        thread_id: str,
        to_agent: str,
        message_type: str,
        subject: str,
        content: str,
        related_task_id: str = "",
        related_artifact_id: str = "",
    ) -> str:
        """在线程内向其他 agent 发送消息。sender 自动绑定为当前 agent。"""
        if message_type not in VALID_MESSAGE_TYPES:
            return f"message_type 无效，可选值：{', '.join(sorted(VALID_MESSAGE_TYPES))}"
        try:
            message = bus.send_message(
                project_id=project_id,
                thread_id=thread_id,
                from_agent=agent_name,
                to_agent=to_agent,
                message_type=message_type,
                subject=subject,
                content=content,
                related_task_id=related_task_id or None,
                related_artifact_id=related_artifact_id or None,
            )
        except Exception as exc:
            return f"发送消息失败: {exc}"
        return _dump(message)

    @tool("read_agent_inbox")
    def read_agent_inbox(project_id: str, thread_id: str = "", unread_only: bool = True) -> str:
        """读取当前 agent 的收件箱，可限制到某个线程。"""
        try:
            items = bus.inbox(
                project_id=project_id,
                recipient=agent_name,
                thread_id=thread_id or None,
                only_pending=unread_only,
            )
        except Exception as exc:
            return f"读取收件箱失败: {exc}"
        if not items:
            return "当前没有待处理消息。"
        return _dump(items)

    @tool("read_thread_messages")
    def read_thread_messages(project_id: str, thread_id: str) -> str:
        """读取线程中的全部消息。"""
        try:
            messages = bus.thread_messages(project_id, thread_id)
        except Exception as exc:
            return f"读取线程消息失败: {exc}"
        if not messages:
            return "该线程当前没有消息。"
        return _dump(messages)

    @tool("mark_message_processed")
    def mark_message_processed(project_id: str, message_id: str) -> str:
        """将消息标记为 processed。"""
        try:
            message = bus.mark_processed(project_id, message_id)
        except Exception as exc:
            return f"标记消息失败: {exc}"
        return _dump(message)

    @tool("mark_message_done")
    def mark_message_done(project_id: str, message_id: str) -> str:
        """兼容旧工具名，等价于 mark_message_processed。"""
        return mark_message_processed(project_id, message_id)

    @tool("list_interaction_threads")
    def list_interaction_threads(project_id: str) -> str:
        """列出项目内全部对话线程。"""
        try:
            threads = bus.list_threads(project_id)
        except Exception as exc:
            return f"读取线程列表失败: {exc}"
        if not threads:
            return "当前没有交互线程。"
        return _dump(threads)

    @tool("update_interaction_thread")
    def update_interaction_thread(project_id: str, thread_id: str, status: str, summary: str = "") -> str:
        """更新线程状态与摘要。"""
        if status not in VALID_THREAD_STATUSES:
            return f"status 无效，可选值：{', '.join(sorted(VALID_THREAD_STATUSES))}"
        try:
            thread = bus.update_thread_status(
                project_id=project_id,
                thread_id=thread_id,
                status=status,
                summary=summary or None,
            )
        except Exception as exc:
            return f"更新线程失败: {exc}"
        return _dump(thread)

    return [
        create_interaction_thread,
        get_interaction_thread,
        send_agent_message,
        read_agent_inbox,
        read_thread_messages,
        mark_message_processed,
        mark_message_done,
        list_interaction_threads,
        update_interaction_thread,
    ]


__all__ = ["get_interaction_tools"]
