from __future__ import annotations

from agent.src.agent.conversation_store import ConversationStore


class MessageBus:
    def __init__(self, store: ConversationStore | None = None) -> None:
        self.store = store or ConversationStore()

    def create_thread(
        self,
        project_id: str,
        title: str,
        goal: str,
        participants: list[str],
        owner: str,
    ):
        return self.store.create_thread(
            project_id=project_id,
            title=title,
            goal=goal,
            participants=participants,
            owner=owner,
        )

    def get_thread(self, project_id: str, thread_id: str):
        return self.store.get_thread(project_id, thread_id)

    def list_threads(self, project_id: str):
        return self.store.list_threads(project_id)

    def send_message(
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
    ):
        return self.store.add_message(
            project_id=project_id,
            thread_id=thread_id,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            subject=subject,
            content=content,
            related_task_id=related_task_id,
            related_artifact_id=related_artifact_id,
        )

    def inbox(
        self,
        project_id: str,
        recipient: str,
        *,
        thread_id: str | None = None,
        only_pending: bool = True,
    ):
        return self.store.get_inbox(
            project_id=project_id,
            recipient=recipient,
            thread_id=thread_id,
            only_pending=only_pending,
        )

    def thread_messages(self, project_id: str, thread_id: str):
        return self.store.list_thread_messages(project_id, thread_id)

    def mark_processed(self, project_id: str, message_id: str):
        return self.store.mark_processed(project_id, message_id)

    def update_thread_status(
        self,
        project_id: str,
        thread_id: str,
        status: str,
        *,
        summary: str | None = None,
    ):
        return self.store.update_thread(project_id, thread_id, status=status, summary=summary)

    def pending_count(
        self,
        project_id: str,
        *,
        thread_id: str | None = None,
        recipient: str | None = None,
    ) -> int:
        return self.store.count_pending_messages(project_id, thread_id=thread_id, recipient=recipient)


_STORE = ConversationStore()
_BUS = MessageBus(store=_STORE)


def get_conversation_store() -> ConversationStore:
    return _STORE


def get_message_bus() -> MessageBus:
    return _BUS


__all__ = ["MessageBus", "get_conversation_store", "get_message_bus"]
