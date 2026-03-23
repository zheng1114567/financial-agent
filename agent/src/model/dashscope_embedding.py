import os
from typing import Iterable, List

from openai import OpenAI

from agent.src.model.qwen import qwen_api_key


class DashScopeEmbeddingClient:
    """
    使用 DashScope 的 compatible OpenAI embeddings 接口。

    說明：
    - 共用現有的 DASHSCOPE_API_KEY。
    - 依賴 openai SDK（langchain_openai 也需要），base_url 與 qwen_llm 相同域名。
    """

    def __init__(
        self,
        model: str = "text-embedding-v1",
        api_key: str | None = None,
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ) -> None:
        self.model = model
        self.api_key = api_key or qwen_api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未設置，無法使用 DashScope embedding。")

        self._client = OpenAI(api_key=self.api_key, base_url=base_url)

    def embed(self, texts: Iterable[str]) -> List[List[float]]:
        """
        同步版本 embedding。
        - texts: 多條文字
        - 返回: 對應的向量列表
        """
        items = list(texts)
        if not items:
            return []

        resp = self._client.embeddings.create(model=self.model, input=items)
        # OpenAI 兼容格式: resp.data[i].embedding
        return [d.embedding for d in resp.data]


__all__ = ["DashScopeEmbeddingClient"]

