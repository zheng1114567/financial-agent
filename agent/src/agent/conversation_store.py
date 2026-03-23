from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from agent.src.agent.interaction_protocol import (
    InteractionMessage,
    InteractionThread,
    VALID_MESSAGE_STATUSES,
    VALID_MESSAGE_TYPES,
    VALID_THREAD_STATUSES,
    utc_now,
)
from agent.src.agent.shared import DATA_ROOT


class ConversationStore:
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or (Path(DATA_ROOT) / "interactions"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_thread(
        self,
        project_id: str,
        title: str,
        goal: str,
        participants: list[str],
        owner: str,
    ) -> InteractionThread:
        normalized_owner = owner.strip()
        normalized_participants = sorted(
            {
                normalized_owner,
                *(item.strip() for item in participants if item and item.strip()),
            }
        )
        thread = InteractionThread(
            id=f"thread-{uuid4().hex[:10]}",
            project_id=project_id.strip(),
            title=title.strip() or "多 agent 交互线程",
            goal=goal.strip(),
            participants=normalized_participants,
            owner=normalized_owner,
        )
        self._write_json(self._thread_path(thread.project_id, thread.id), asdict(thread))
        return thread

    def list_threads(self, project_id: str) -> list[InteractionThread]:
        thread_dir = self._threads_dir(project_id)
        threads: list[InteractionThread] = []
        for path in sorted(thread_dir.glob("*.json")):
            payload = self._read_json(path)
            if payload:
                threads.append(InteractionThread(**payload))
        threads.sort(key=lambda item: item.updated_at, reverse=True)
        return threads

    def get_thread(self, project_id: str, thread_id: str) -> InteractionThread:
        payload = self._read_json(self._thread_path(project_id, thread_id))
        if not payload:
            raise FileNotFoundError(f"thread not found: {thread_id}")
        return InteractionThread(**payload)

    def update_thread(
        self,
        project_id: str,
        thread_id: str,
        *,
        status: str | None = None,
        summary: str | None = None,
    ) -> InteractionThread:
        thread = self.get_thread(project_id, thread_id)
        if status is not None:
            if status not in VALID_THREAD_STATUSES:
                raise ValueError(f"invalid thread status: {status}")
            thread.status = status  # type: ignore[assignment]
        if summary is not None:
            thread.summary = summary
        thread.updated_at = utc_now()
        self._write_json(self._thread_path(project_id, thread_id), asdict(thread))
        return thread

    def add_message(
        self,
        project_id: str,
        thread_id: str,
        from_agent: str,
        to_agent: str,
        message_type: str,
        subject: str,
        content: str,
        *,
        related_task_id: str | None = None,
        related_artifact_id: str | None = None,
    ) -> InteractionMessage:
        if message_type not in VALID_MESSAGE_TYPES:
            raise ValueError(f"invalid message type: {message_type}")

        thread = self.get_thread(project_id, thread_id)
        normalized_sender = from_agent.strip()
        normalized_recipient = to_agent.strip()
        if normalized_sender not in thread.participants and normalized_sender != "user":
            raise ValueError(f"sender is not part of thread: {normalized_sender}")
        if normalized_recipient not in thread.participants:
            raise ValueError(f"recipient is not part of thread: {normalized_recipient}")

        message = InteractionMessage(
            id=f"msg-{uuid4().hex[:12]}",
            thread_id=thread_id,
            project_id=project_id,
            from_agent=normalized_sender,
            to_agent=normalized_recipient,
            message_type=message_type,  # type: ignore[arg-type]
            subject=subject.strip() or message_type,
            content=content.strip(),
            related_task_id=related_task_id or None,
            related_artifact_id=related_artifact_id or None,
        )
        self._write_json(self._message_path(project_id, message.id), asdict(message))

        next_status = "in_progress" if thread.status == "open" else thread.status
        self.update_thread(project_id, thread_id, status=next_status)
        return message

    def list_thread_messages(self, project_id: str, thread_id: str) -> list[InteractionMessage]:
        messages = [message for message in self._all_messages(project_id) if message.thread_id == thread_id]
        messages.sort(key=lambda item: item.created_at)
        return messages

    def get_inbox(
        self,
        project_id: str,
        recipient: str,
        *,
        thread_id: str | None = None,
        only_pending: bool = True,
        only_unread: bool | None = None,
    ) -> list[InteractionMessage]:
        if only_unread is not None:
            only_pending = only_unread
        items = self.list_thread_messages(project_id, thread_id) if thread_id else self._all_messages(project_id)
        recipient = recipient.strip()
        results = [
            item
            for item in items
            if item.to_agent == recipient and (not only_pending or item.status == "pending")
        ]
        results.sort(key=lambda item: item.created_at)
        return results

    def mark_message_status(self, project_id: str, message_id: str, status: str) -> InteractionMessage:
        if status not in VALID_MESSAGE_STATUSES:
            raise ValueError(f"invalid message status: {status}")
        path = self._message_path(project_id, message_id)
        payload = self._read_json(path)
        if not payload:
            raise FileNotFoundError(f"message not found: {message_id}")

        message = InteractionMessage(**payload)
        message.status = status  # type: ignore[assignment]
        message.updated_at = utc_now()
        message.processed_at = message.updated_at if status == "processed" else None
        self._write_json(path, asdict(message))
        self._touch_thread(project_id, message.thread_id)
        return message

    def mark_processed(self, project_id: str, message_id: str) -> InteractionMessage:
        return self.mark_message_status(project_id, message_id, "processed")

    def count_pending_messages(
        self,
        project_id: str,
        *,
        thread_id: str | None = None,
        recipient: str | None = None,
    ) -> int:
        messages = self.list_thread_messages(project_id, thread_id) if thread_id else self._all_messages(project_id)
        return sum(
            1
            for message in messages
            if message.status == "pending"
            and (recipient is None or message.to_agent == recipient)
        )

    def _touch_thread(self, project_id: str, thread_id: str) -> None:
        thread = self.get_thread(project_id, thread_id)
        thread.updated_at = utc_now()
        self._write_json(self._thread_path(project_id, thread_id), asdict(thread))

    def _all_messages(self, project_id: str) -> list[InteractionMessage]:
        message_dir = self._messages_dir(project_id)
        messages: list[InteractionMessage] = []
        for path in sorted(message_dir.glob("*.json")):
            payload = self._read_json(path)
            if payload:
                messages.append(InteractionMessage(**payload))
        messages.sort(key=lambda item: item.created_at)
        return messages

    def _project_dir(self, project_id: str) -> Path:
        project_dir = self.base_dir / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        return project_dir

    def _threads_dir(self, project_id: str) -> Path:
        thread_dir = self._project_dir(project_id) / "threads"
        thread_dir.mkdir(parents=True, exist_ok=True)
        return thread_dir

    def _messages_dir(self, project_id: str) -> Path:
        message_dir = self._project_dir(project_id) / "messages"
        message_dir.mkdir(parents=True, exist_ok=True)
        return message_dir

    def _thread_path(self, project_id: str, thread_id: str) -> Path:
        return self._threads_dir(project_id) / f"{thread_id}.json"

    def _message_path(self, project_id: str, message_id: str) -> Path:
        return self._messages_dir(project_id) / f"{message_id}.json"

    def _write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read_json(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["ConversationStore"]
