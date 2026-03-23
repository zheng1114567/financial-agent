from __future__ import annotations

import os
import sys


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# 当前仓库根目录本身就是 agent 根目录，避免拼成 agent/agent。
AGENT_ROOT = PROJECT_ROOT
DATA_ROOT = os.path.join(PROJECT_ROOT, "data")


def ensure_project_root_on_path() -> None:
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)


ensure_project_root_on_path()


def create_memory_agent(
    storage_filename: str,
    *,
    use_llm_scoring: bool = True,
):
    from agent.src.model.dashscope_embedding import DashScopeEmbeddingClient
    from agent.src.rag.embedding_memory_store import EmbeddingMemoryStore
    from agent.src.tool.memory_tools import MemoryAgent

    storage_path = os.path.join(DATA_ROOT, storage_filename)
    vector_store = None

    try:
        embedding_client = DashScopeEmbeddingClient()
        vector_store = EmbeddingMemoryStore(
            embedding_client=embedding_client,
            storage_path=storage_path,
        )
    except Exception:
        vector_store = None

    return MemoryAgent(
        vector_store=vector_store,
        use_llm_scoring=use_llm_scoring,
    )


__all__ = [
    "PROJECT_ROOT",
    "AGENT_ROOT",
    "DATA_ROOT",
    "ensure_project_root_on_path",
    "create_memory_agent",
]
