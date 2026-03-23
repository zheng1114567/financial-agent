from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


InteractionMessageType = Literal[
    "request",
    "question",
    "proposal",
    "critique",
    "handoff",
    "status",
    "decision",
    "blocker",
]
InteractionMessageStatus = Literal["pending", "processed"]
InteractionThreadStatus = Literal[
    "open",
    "in_progress",
    "blocked",
    "resolved",
    "closed",
]


VALID_MESSAGE_TYPES = {
    "request",
    "question",
    "proposal",
    "critique",
    "handoff",
    "status",
    "decision",
    "blocker",
}
VALID_MESSAGE_STATUSES = {"pending", "processed"}
VALID_THREAD_STATUSES = {
    "open",
    "in_progress",
    "blocked",
    "resolved",
    "closed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class InteractionThread:
    id: str
    project_id: str
    title: str
    goal: str
    participants: list[str]
    owner: str
    status: InteractionThreadStatus = "open"
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class InteractionMessage:
    id: str
    thread_id: str
    project_id: str
    from_agent: str
    to_agent: str
    message_type: InteractionMessageType
    subject: str
    content: str
    related_task_id: str | None = None
    related_artifact_id: str | None = None
    status: InteractionMessageStatus = "pending"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    processed_at: str | None = None


# Backward-compatible aliases for older imports.
MessageRecord = InteractionMessage
MessageStatus = InteractionMessageStatus
MessageType = InteractionMessageType
ThreadRecord = InteractionThread
ThreadStatus = InteractionThreadStatus


__all__ = [
    "InteractionMessage",
    "InteractionMessageStatus",
    "InteractionMessageType",
    "InteractionThread",
    "InteractionThreadStatus",
    "MessageRecord",
    "MessageStatus",
    "MessageType",
    "ThreadRecord",
    "ThreadStatus",
    "VALID_MESSAGE_STATUSES",
    "VALID_MESSAGE_TYPES",
    "VALID_THREAD_STATUSES",
    "utc_now",
]
