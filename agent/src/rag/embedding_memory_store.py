import json
import math
import os
import threading
import time
from dataclasses import asdict, dataclass
from typing import List, Literal, Optional

from agent.src.model.dashscope_embedding import DashScopeEmbeddingClient


MemoryContentType = Literal["user_memory", "project_decision"]


@dataclass
class StoredMemory:
    id: str
    text: str
    embedding: List[float]
    type: MemoryContentType
    created_at: float
    last_used_at: float
    importance: float
    source: Optional[str] = None


class EmbeddingMemoryStore:
    """
    非常簡單的本地向量記憶庫實現：
    - 使用 DashScopeEmbeddingClient 生成向量
    - 記憶保存在內存，並定期寫入 JSONL 檔（追加式）
    - 搜索時用純 Python 計算餘弦相似度

    設計目標：
    - 先讓 RAG 記憶流程跑起來，之後你可以替換為 Chroma / FAISS 等更專業的向量庫。
    """

    def __init__(
        self,
        embedding_client: Optional[DashScopeEmbeddingClient],
        storage_path: str,
    ) -> None:
        self.embedding_client = embedding_client
        self.storage_path = storage_path
        self._memories: List[StoredMemory] = []
        self._lock = threading.Lock()

        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        self._load_from_disk()

    # ===== 對外接口 =====

    def add_memory(
        self,
        text: str,
        mtype: MemoryContentType,
        importance: float,
        source: Optional[str] = None,
    ) -> None:
        if self.embedding_client is None:
            return
        emb = self.embedding_client.embed([text])[0]
        now = time.time()
        mid = f"{int(now * 1000)}-{len(self._memories)}"
        memory = StoredMemory(
            id=mid,
            text=text,
            embedding=emb,
            type=mtype,
            created_at=now,
            last_used_at=now,
            importance=importance,
            source=source,
        )
        with self._lock:
            self._memories.append(memory)
            self._append_to_disk(memory)

    def compact(
        self,
        max_items: int = 2000,
        min_importance: float = 0.0,
    ) -> None:
        """
        對內存與磁碟上的向量記憶做一次輕量級壓縮：
        - 優先保留 importance 較高、最近使用的記憶
        - 將結果整體重寫回 JSONL 文件，避免無限制追加導致文件膨脹
        """
        with self._lock:
            if not self._memories:
                return

            now = time.time()

            def _score(m: StoredMemory) -> float:
                # 使用簡單衰減模型：越新的 last_used_at 得分越高
                age_days = max(0.0, (now - (m.last_used_at or m.created_at)) / 86400.0)
                recency_factor = 1.0 / (1.0 + age_days)
                return m.importance * 2.0 + recency_factor

            # 先按重要度與最近使用排序
            kept = [
                m for m in self._memories if m.importance >= min_importance
            ] or list(self._memories)

            kept.sort(key=_score, reverse=True)
            if len(kept) > max_items:
                kept = kept[:max_items]

            # 覆蓋內存與磁碟文件
            self._memories = kept
            try:
                with open(self.storage_path, "w", encoding="utf-8") as f:
                    for m in self._memories:
                        f.write(json.dumps(asdict(m), ensure_ascii=False) + "\n")
            except Exception:
                # 壓縮失敗不影響主流程
                pass

    def search(
        self,
        query: str,
        mtype: Optional[MemoryContentType] = None,
        k: int = 5,
    ) -> List[StoredMemory]:
        if not self._memories:
            return []
        if self.embedding_client is None:
            query_terms = {term for term in query.lower().split() if term}
            if not query_terms:
                return []

            def keyword_score(memory: StoredMemory) -> int:
                text_terms = set(memory.text.lower().split())
                return len(query_terms & text_terms)

            with self._lock:
                candidates = [
                    m for m in self._memories if (mtype is None or m.type == mtype)
                ]

            scored = [(keyword_score(m), m) for m in candidates]
            scored.sort(key=lambda item: item[0], reverse=True)
            return [memory for score, memory in scored[:k] if score > 0]

        q_emb = self.embedding_client.embed([query])[0]

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            na = math.sqrt(sum(x * x for x in a))
            nb = math.sqrt(sum(y * y for y in b))
            if na == 0 or nb == 0:
                return 0.0
            return dot / (na * nb)

        with self._lock:
            candidates = [
                m for m in self._memories if (mtype is None or m.type == mtype)
            ]

        scored = [
            (cosine(q_emb, m.embedding), m)
            for m in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        top = [m for score, m in scored[:k] if score > 0]
        now = time.time()
        for m in top:
            m.last_used_at = now

        return top

    # ===== 持久化相關 =====

    def _append_to_disk(self, memory: StoredMemory) -> None:
        try:
            with open(self.storage_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(memory), ensure_ascii=False) + "\n")
        except Exception:
            # 失敗不影響主流程
            pass

    def _load_from_disk(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    self._memories.append(
                        StoredMemory(
                            id=data["id"],
                            text=data["text"],
                            embedding=data["embedding"],
                            type=data.get("type", "user_memory"),
                            created_at=data.get("created_at", time.time()),
                            last_used_at=data.get("last_used_at", time.time()),
                            importance=data.get("importance", 0.0),
                            source=data.get("source"),
                        )
                    )
        except Exception:
            # 讀取問題時不阻塞主流程
            self._memories = []


__all__ = ["EmbeddingMemoryStore", "StoredMemory", "MemoryContentType"]

