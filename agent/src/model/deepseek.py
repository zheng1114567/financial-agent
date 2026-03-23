import os

from langchain_openai import ChatOpenAI


deepseek_api_key = os.environ.get("DEEPSEEK_API_KEY")
MODEL_NAME = "deepseek-chat"

deepseek_llm = ChatOpenAI(
    model=MODEL_NAME,
    base_url="https://api.deepseek.com/v1",
    api_key= deepseek_api_key,
    streaming=True,
    temperature=0.7
)

