import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from langchain_core.tools import tool

from agent.src.model.qwen import qwen_llm
from agent.src.rag.embedding_memory_store import EmbeddingMemoryStore


MemoryType = Literal["short_term", "long_term"]
MemoryCategory = Literal[
    "preference",      # 用戶偏好 / 習慣 / 風格
    "environment",     # 環境配置（路徑、系統、工具鏈等）
    "goal",            # 長期目標
    "task_context",    # 單次任務上下文
    "other",           # 其它無法明確分類的信息
]


@dataclass
class MemoryItem:
    """单条记忆数据结构"""

    text: str
    memory_type: MemoryType
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)
    last_used_at: Optional[datetime.datetime] = None
    importance: float = 0.0
    source: str | None = None
    category: MemoryCategory = "other"


class MemoryAgent:
    """
    MemoryAgent:
    - 维护短期 / 长期记忆
    - 提供 recall() 供其他 Agent 在回答前取得上下文
    - 提供 process_interaction() 在一次对话结束后决定是否写入长期记忆

    """

    def __init__(
        self,
        max_short_term: int = 20,
        long_term_threshold: float = 0.6,
        vector_store: Optional[EmbeddingMemoryStore] = None,
        use_llm_scoring: bool = True,
        max_long_term: int = 512,
    ) -> None:
        self.max_short_term = max_short_term
        self.long_term_threshold = long_term_threshold
        self._use_llm_scoring = use_llm_scoring

        self._short_term: List[MemoryItem] = []
        self._long_term: List[MemoryItem] = []
        self._vector_store = vector_store
        self._max_long_term = max_long_term
        # 用於觸發定期維護（清理 / 壓縮）邏輯
        self._interaction_count: int = 0

        # 針對不同記憶類別設置不同的長期記憶閾值與保留策略
        # 數值越低越容易寫入長期記憶
        self._category_threshold: Dict[MemoryCategory, float] = {
            "preference": 0.4,     # 用戶偏好通常很重要，閾值略低
            "environment": 0.5,
            "goal": 0.4,
            "task_context": 0.7,   # 單次任務上下文，多為一次性信息，閾值較高
            "other": 0.7,
        }

    # ===== 公共接口 =====

    def recall(self, query: str) -> dict:
        """
        提供给其他 Agent 使用：
        - 返回当前的短期记忆（最近几条）
        - 以及跟 query 粗略相关的长期记忆（优先用向量检索）
        """
        short_term_texts = [m.text for m in self._short_term[-self.max_short_term :]]

        # 長期記憶：優先使用向量檢索；如無向量庫則退回關鍵字粗篩
        related_long_term_texts: List[str] = []

        if not query.strip():
            related_long_term_texts = [m.text for m in self._long_term[-8:]]
        elif self._vector_store and getattr(self._vector_store, "embedding_client", None) is not None:
            hits = self._vector_store.search(query, mtype="user_memory", k=8)
            related_long_term_texts = [m.text for m in hits]
        else:
            query_lower = query.lower()
            related_long_term: List[MemoryItem] = []
            for item in self._long_term:
                if any(word in item.text.lower() for word in query_lower.split()):
                    related_long_term.append(item)

            # 更新 last_used_at 与 importance（简单增强）
            now = datetime.datetime.now(datetime.timezone.utc)
            for item in related_long_term:
                item.last_used_at = now
                item.importance = min(1.0, item.importance + 0.05)

            related_long_term_texts = [m.text for m in related_long_term]

        # 如果檢索到多條長期記憶，使用 LLM 做一次針對 query 的壓縮與衝突消解，
        # 同時也能在多義詞場景下只保留與當前語境相關的那一部分含義。
        if (
            related_long_term_texts
            and len(related_long_term_texts) > 1
            and self._use_llm_scoring
            and qwen_llm is not None
        ):
            try:
                summary_prompt = (
                    "下面是多條與用戶相關的長期記憶條目，可能存在重複或相互矛盾，"
                    "也可能包含同一詞語在不同語境下的多種含義。\n"
                    "當前用戶的查詢為：\n"
                    f"{query}\n\n"
                    "請你完成以下任務：\n"
                    "1. 僅保留與當前查詢最相關的要點；\n"
                    "2. 如果記憶之間對同一事實存在衝突，請根據時間線與合理性進行合併與糾正，"
                    "   給出一份一致且可執行的結論；\n"
                    "3. 對重複信息做去重與壓縮，輸出 3~8 條簡短的條目，每條獨立成行。\n\n"
                    "請直接輸出整理後的條目，每行一條，不要添加額外說明。\n\n"
                    "以下是原始記憶條目：\n"
                    + "\n".join(f"- {t}" for t in related_long_term_texts)
                )
                llm_result = qwen_llm.invoke(summary_prompt)
                merged = (
                    getattr(llm_result, "content", None)
                    or getattr(llm_result, "text", None)
                    or str(llm_result)
                )
                # 清洗輸出為行列表
                merged_lines = [
                    line.strip("- ").strip()
                    for line in str(merged).splitlines()
                    if line.strip()
                ]
                if merged_lines:
                    related_long_term_texts = merged_lines
            except Exception:
                # 如果合併失敗，回退到原始檢索結果
                pass

        return {
            "short_term": short_term_texts,
            "long_term": related_long_term_texts,
        }

    def process_interaction(
        self,
        user_input: str,
        agent_output: str,
        source: str | None = None,
    ) -> None:
        """
        在一次 user_input → agent_output 结束后调用：
        - 更新短期记忆
        - 对候选信息打分，决定是否写入长期记忆
        """
        interaction_summary = self._summarize_interaction(user_input, agent_output)

        # 总是先加入短期记忆
        self._add_short_term(interaction_summary, source=source)

        # 判斷記憶類別
        category = self._classify_category(interaction_summary)

        # 计算长期记忆分数
        score = self._score_for_long_term(interaction_summary, category=category)
        category_threshold = self._category_threshold.get(category, self.long_term_threshold)
        if score >= category_threshold:
            self._add_long_term(
                interaction_summary,
                importance=score,
                source=source,
                category=category,
            )

        # 記一次交互，用於觸發定期維護
        self._interaction_count += 1
        # 每 20 輪對話做一次輕量級維護與壓縮，避免長期記憶無限制增長
        if self._interaction_count % 20 == 0:
            self.maintenance_tick()

    # ===== 内部方法 =====

    def _add_short_term(
        self,
        text: str,
        source: str | None = None,
        category: MemoryCategory = "other",
    ) -> None:
        self._short_term.append(
            MemoryItem(
                text=text,
                memory_type="short_term",
                importance=0.0,
                source=source,
                category=category,
            )
        )
        # 控制长度
        if len(self._short_term) > self.max_short_term:
            overflow = len(self._short_term) - self.max_short_term
            self._short_term = self._short_term[overflow:]

    def _add_long_term(
        self,
        text: str,
        importance: float,
        source: str | None = None,
        category: MemoryCategory = "other",
    ) -> None:
        item = MemoryItem(
            text=text,
            memory_type="long_term",
            importance=importance,
            source=source,
            category=category,
        )
        self._long_term.append(item)

        # 控制內存中長期記憶總量，優先保留「重要且較新的」記憶
        if len(self._long_term) > self._max_long_term:
            self._shrink_long_term_in_memory()

        # 同步寫入向量記憶庫，方便之後做語義檢索
        if self._vector_store:
            try:
                self._vector_store.add_memory(
                    text=text,
                    mtype="user_memory",
                    importance=importance,
                    source=source,
                )
            except Exception:
                # 寫入失敗不影響主流程
                pass

    def _shrink_long_term_in_memory(self) -> None:
        """
        根據 importance 與 created_at 對內存中的長期記憶做簡單排序與截斷，
        防止無限制增長導致召回時噪音過多。
        """
        if not self._long_term:
            return

        def _score(m: MemoryItem) -> float:
            ts = m.last_used_at or m.created_at
            # 以時間戳做輕量級衰減：越新的得分越高
            t_weight = ts.timestamp() if isinstance(ts, datetime.datetime) else 0.0
            return m.importance * 10.0 + t_weight / 10_000_000_000.0

        self._long_term.sort(key=_score, reverse=True)
        self._long_term = self._long_term[: self._max_long_term]

    def maintenance_tick(self) -> None:
        """
        由外部週期性調用的維護入口：
        - 對內存中的長期記憶做整理與截斷
        - 通知向量記憶庫做一次壓縮（如果實現的話）
        """
        # 整理 Python 進程內的長期記憶
        self._shrink_long_term_in_memory()

        # 如果向量記憶庫支持壓縮，則做一次輕量級 compact
        if self._vector_store and hasattr(self._vector_store, "compact"):
            try:
                # 傾向保留重要記憶與最近使用的記憶
                self._vector_store.compact(
                    max_items=2000,
                    min_importance=0.3,
                )
            except Exception:
                # 壓縮失敗不阻塞主流程
                pass

    def _summarize_interaction(self, user_input: str, agent_output: str) -> str:
        """
        对一次交互做简要摘要，作为记忆条目。
        这里仍然用简单拼接，你可以以后改成 LLM 摘要。
        """
        user_input = user_input.strip()
        agent_output = agent_output.strip()
        if not user_input and not agent_output:
            return ""

        return f"用户说: {user_input}\nAgent 回复关键信息: {agent_output}"

    def _classify_category(self, text: str) -> MemoryCategory:
        """
        使用 Qwen 對記憶條目進行類別判斷：
        - preference: 用戶偏好 / 習慣 / 風格要求
        - environment: 環境配置（路徑、系統、工具鏈、版本等）
        - goal: 長期目標或需要多輪才能完成的任務
        - task_context: 單輪或短期任務的具體上下文
        - other: 其它無法明確歸類的信息
        """
        if not (self._use_llm_scoring and qwen_llm is not None):
            return "other"

        prompt = (
            "你是一个记忆分类助手。下面是一段关于用户与助手交互的摘要，请判断它最适合归为哪一类记忆。\n"
            "可选类别只有以下五个（必须严格输出其中之一的英文小写單詞）：\n"
            "1. preference: 用户偏好、习惯、写作/编码风格、语言偏好等稳定偏好；\n"
            "2. environment: 项目路径、本地/远程环境配置、依赖版本、系统信息等；\n"
            "3. goal: 用户的中长期目标、持续要推进的任务；\n"
            "4. task_context: 某一次具体任务的上下文信息，只在当前/少数几轮对话中有用；\n"
            "5. other: 其它不属于以上四类的信息。\n\n"
            "请只输出以上五个英文标签之一（preference/environment/goal/task_context/other），不要输出任何其它内容。\n\n"
            f"待分类的交互摘要：\n{text}\n"
        )

        try:
            result = qwen_llm.invoke(prompt)
            raw = getattr(result, "content", None) or getattr(result, "text", None) or str(result)
            label = str(raw).strip().split()[0].lower()
            if label in {"preference", "environment", "goal", "task_context", "other"}:
                return label  # type: ignore[return-value]
        except Exception:
            pass

        return "other"

    def _score_for_long_term(self, text: str, category: MemoryCategory = "other") -> float:
        """
        仅使用 Qwen LLM 给出 0.0~1.0 的长期记忆评分：
        - LLM 负责语义理解（HIGH / MEDIUM / LOW），再映射为数值
        """
        text = text.strip()
        if not text:
            return 0.0

        if not (self._use_llm_scoring and qwen_llm is not None):
            return 0.0

        try:
            prompt = (
                "你是一个记忆管理助手。下面是一段关于用户与助手交互的摘要，以及它所属的记忆类别。\n"
                "请判断这段信息在该类别下是否具有长期价值，给出 HIGH / MEDIUM / LOW 之一：\n"
                "- HIGH（很重要，应该几乎一定写入长期记忆，例如用户的长期偏好、语言习惯、项目路径等）\n"
                "- MEDIUM（有一定帮助，可以写入长期记忆）\n"
                "- LOW（一次性信息，没有必要写入长期记忆）\n\n"
                f"当前记忆类别：{category}\n"
                "交互摘要如下：\n"
                f"{text}\n"
                "请只输出 HIGH、MEDIUM 或 LOW 其中一个单词，不要输出任何其它内容。\n"
            )
            llm_result = qwen_llm.invoke(prompt)
            if hasattr(llm_result, "content"):
                raw = str(llm_result.content).strip()
            else:
                raw = str(llm_result).strip()

            label = raw.strip().upper().split()[0]
            mapping = {
                "HIGH": 0.95,
                "MEDIUM": 0.7,
                "LOW": 0.2,
            }
            score = mapping.get(label, 0.0)
        except Exception:
            score = 0.0

        return max(0.0, min(1.0, score))


def get_memory_tools(memory_agent: MemoryAgent) -> List:
    """
    基于给定的 MemoryAgent 实例，构造一组可供 LLM 调用的工具。
    注意：这些工具只是「辅助查看/总结记忆」，核心长短期判断仍由 MemoryAgent 自己在程序内部完成。
    """

    @tool("show_memory")
    def show_memory() -> str:
        """
        查看当前已存的短期与长期记忆摘要，方便你在回答前自检记忆内容。
        """
        ctx = memory_agent.recall("")  # 用空 query 取出最近短期 & 全部长期的粗略集合
        short_term = ctx.get("short_term") or []
        long_term = ctx.get("long_term") or []

        parts: list[str] = []
        if short_term:
            parts.append("【短期记忆】\n" + "\n".join(short_term))
        if long_term:
            parts.append("【长期记忆】\n" + "\n".join(long_term))
        if not parts:
            return "当前还没有可用的记忆记录。"
        return "\n\n".join(parts)

    @tool("inspect_memory_by_category")
    def inspect_memory_by_category(category: str) -> str:
        """
        按类别可视化当前记忆狀態。
        可選類別：
        - preference: 用户偏好 / 风格
        - environment: 环境配置
        - goal: 长期目标
        - task_context: 单次任务上下文
        - other: 其它
        如传入 'all' 則顯示所有類別的簡要統計信息。
        """
        cat = category.strip().lower()
        valid = {"preference", "environment", "goal", "task_context", "other", "all"}
        if cat not in valid:
            return (
                "无效的类别。請在以下值中選擇："
                "preference / environment / goal / task_context / other / all"
            )

        lines: list[str] = []
        # 直接訪問內部記憶結構
        long_term = getattr(memory_agent, "_long_term", [])
        short_term = getattr(memory_agent, "_short_term", [])

        if cat == "all":
            # 統計信息視圖
            from collections import Counter

            lt_counter = Counter(getattr(m, "category", "other") for m in long_term)
            st_counter = Counter(getattr(m, "category", "other") for m in short_term)

            lines.append("【長期記憶統計】")
            for k, v in lt_counter.items():
                lines.append(f"- {k}: {v} 條")

            lines.append("\n【短期記憶統計】")
            for k, v in st_counter.items():
                lines.append(f"- {k}: {v} 條")

            return "\n".join(lines)

        def _fmt_item(idx: int, m: MemoryItem) -> str:
            ts = m.created_at.isoformat(timespec="seconds")
            last = m.last_used_at.isoformat(timespec="seconds") if m.last_used_at else "-"
            return (
                f"[{idx}]({m.memory_type}) importance={m.importance:.2f} "
                f"created_at={ts} last_used_at={last}\n{m.text}"
            )

        lines.append(f"【類別 = {cat} 的長期記憶】")
        filtered_lt = [
            m for m in long_term if getattr(m, "category", "other") == cat
        ]
        if not filtered_lt:
            lines.append("(無長期記憶)")
        else:
            for i, m in enumerate(filtered_lt[:50]):
                lines.append(_fmt_item(i, m))

        lines.append(f"\n【類別 = {cat} 的短期記憶】")
        filtered_st = [
            m for m in short_term if getattr(m, "category", "other") == cat
        ]
        if not filtered_st:
            lines.append("(無短期記憶)")
        else:
            for i, m in enumerate(filtered_st[:50]):
                lines.append(_fmt_item(i, m))

        return "\n".join(lines)

    @tool("delete_long_term_memory")
    def delete_long_term_memory(category: str, index: int) -> str:
        """
        手動刪除某一條長期記憶。
        - category: 記憶類別（preference/environment/goal/task_context/other）
        - index: 可從 inspect_memory_by_category(category) 顯示的索引中選擇
        只會刪除內存中的長期記憶，不會立刻重寫向量庫文件（由後續 maintenance_tick 統一整理）。
        """
        cat = category.strip().lower()
        valid = {"preference", "environment", "goal", "task_context", "other"}
        if cat not in valid:
            return (
                "无效的类别。請在以下值中選擇："
                "preference / environment / goal / task_context / other"
            )

        long_term = getattr(memory_agent, "_long_term", [])
        filtered_indices = [
            i for i, m in enumerate(long_term) if getattr(m, "category", "other") == cat
        ]
        if not filtered_indices:
            return f"類別 {cat} 當前沒有任何長期記憶。"

        if index < 0 or index >= len(filtered_indices):
            return f"索引超出範圍，請先調用 inspect_memory_by_category('{cat}') 查看可用索引。"

        real_idx = filtered_indices[index]
        removed = long_term.pop(real_idx)
        setattr(memory_agent, "_long_term", long_term)

        # 後續由 maintenance_tick 負責與向量庫對齊/壓縮
        return (
            "已刪除一條長期記憶：\n"
            f"類別={removed.category}, importance={removed.importance:.2f}\n"
            f"內容=\n{removed.text}"
        )

    @tool("clear_memory_category")
    def clear_memory_category(category: str, scope: str = "long_term") -> str:
        """
        清空某一類別的記憶。
        - category: preference/environment/goal/task_context/other
        - scope: 'long_term'（只清空長期）或 'short_term' 或 'both'
        請謹慎使用，操作不可恢復。
        """
        cat = category.strip().lower()
        valid_cat = {"preference", "environment", "goal", "task_context", "other"}
        if cat not in valid_cat:
            return (
                "无效的类别。請在以下值中選擇："
                "preference / environment / goal / task_context / other"
            )

        scope = scope.strip().lower()
        valid_scope = {"long_term", "short_term", "both"}
        if scope not in valid_scope:
            return "无效的 scope，請使用 long_term / short_term / both。"

        lt = getattr(memory_agent, "_long_term", [])
        st = getattr(memory_agent, "_short_term", [])

        removed_lt = 0
        removed_st = 0

        if scope in {"long_term", "both"}:
            new_lt = [m for m in lt if getattr(m, "category", "other") != cat]
            removed_lt = len(lt) - len(new_lt)
            lt = new_lt
            setattr(memory_agent, "_long_term", lt)

        if scope in {"short_term", "both"}:
            new_st = [m for m in st if getattr(m, "category", "other") != cat]
            removed_st = len(st) - len(new_st)
            st = new_st
            setattr(memory_agent, "_short_term", st)

        return (
            f"已清空類別 {cat} 的記憶："
            f"刪除長期 {removed_lt} 條，刪除短期 {removed_st} 條。"
        )

    return [show_memory, inspect_memory_by_category, delete_long_term_memory, clear_memory_category]


__all__ = ["MemoryAgent", "MemoryItem", "MemoryType", "MemoryCategory", "get_memory_tools"]


