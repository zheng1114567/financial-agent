import os

from langchain_openai import ChatOpenAI


qwen_api_key = os.environ.get("DASHSCOPE_API_KEY")
MODEL_NAME = "qwen-plus"

qwen_llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=qwen_api_key,
    streaming=True,
    temperature=0.7,
    max_retries=3,
    timeout=60,
)

