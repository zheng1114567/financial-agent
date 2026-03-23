from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    PermissionDeniedError,
    RateLimitError,
)
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from agent.src.agent.shared import create_memory_agent
from agent.src.model.qwen import qwen_llm
from agent.src.tool.memory_tools import MemoryAgent


ContextBuilder = Callable[[str], list[SystemMessage] | Awaitable[list[SystemMessage]]]
ToolLoader = Callable[[MemoryAgent], Awaitable[list]]


@dataclass
class AgentSpec:
    name: str
    thread_id: str
    source: str
    display_name: str
    log_prefix: str
    memory_filename: str
    system_instruction: str
    short_term_label: str
    long_term_label: str
    tool_loader: ToolLoader
    context_builder: Optional[ContextBuilder] = None
    use_llm_scoring: bool = True
    max_retries: int = 5
    retry_backoff_seconds: float = 2.0


class AgentRuntime:
    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec
        self.memory_agent: MemoryAgent = create_memory_agent(
            spec.memory_filename,
            use_llm_scoring=spec.use_llm_scoring,
        )
        self._graph = None

    async def initialize(self) -> None:
        if self._graph is not None:
            return
        tools = await self.spec.tool_loader(self.memory_agent)
        self._graph = create_agent(model=qwen_llm, tools=tools)

    async def run_once(
        self,
        user_input: str,
        *,
        stream_to_stdout: bool = False,
        conversation_thread_id: str | None = None,
    ) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.spec.max_retries + 1):
            try:
                return await self._run_once_impl(
                    user_input,
                    stream_to_stdout=stream_to_stdout,
                    conversation_thread_id=conversation_thread_id,
                )
            except Exception as exc:
                if not self._is_retriable_error(exc):
                    raise
                last_error = exc
                if attempt >= self.spec.max_retries:
                    raise
                self._graph = None
                if stream_to_stdout:
                    print(
                        f"{self.spec.log_prefix} 模型调用失败，第 {attempt} 次重试：{type(exc).__name__}: {exc}"
                    )
                await asyncio.sleep(self.spec.retry_backoff_seconds * attempt)
        if last_error is not None:
            raise last_error
        return ""

    def _is_retriable_error(self, exc: Exception) -> bool:
        if isinstance(
            exc,
            (APIConnectionError, APITimeoutError, RateLimitError, APIError, PermissionDeniedError),
        ):
            return True

        message = f"{type(exc).__name__}: {exc}"
        transient_markers = [
            "APIConnectionError",
            "APITimeoutError",
            "RateLimitError",
            "PermissionDeniedError",
            "Workspace.AccessDenied",
            "Connection error",
            "ExceptionGroup",
        ]
        return any(marker in message for marker in transient_markers)

    async def _run_once_impl(
        self,
        user_input: str,
        *,
        stream_to_stdout: bool = False,
        conversation_thread_id: str | None = None,
    ) -> str:
        await self.initialize()
        memory_ctx = await asyncio.to_thread(self.memory_agent.recall, user_input)
        short_term = memory_ctx.get("short_term", [])
        long_term = memory_ctx.get("long_term", [])

        memory_messages: list[SystemMessage] = []
        if short_term:
            memory_messages.append(
                SystemMessage(content=self.spec.short_term_label + "\n" + "\n".join(short_term))
            )
        if long_term:
            memory_messages.append(
                SystemMessage(content=self.spec.long_term_label + "\n" + "\n".join(long_term))
            )

        context_messages: list[SystemMessage] = []
        if self.spec.context_builder is not None:
            maybe_messages = self.spec.context_builder(user_input)
            if inspect.isawaitable(maybe_messages):
                context_messages = await maybe_messages
            else:
                context_messages = maybe_messages

        input_messages = [
            SystemMessage(content=self.spec.system_instruction),
            *memory_messages,
            *context_messages,
            HumanMessage(content=user_input),
        ]

        config = RunnableConfig(
            configurable={"thread_id": conversation_thread_id or self.spec.thread_id}
        )
        last_plain_answer_parts: list[str] = []

        async for event in self._graph.astream(
            {"messages": input_messages},
            config=config,
            stream_mode="updates",
        ):
            if not stream_to_stdout:
                self._collect_plain_parts(event, last_plain_answer_parts)
                continue

            for node_name, node_output in event.items():
                if "messages" not in node_output:
                    continue
                for msg in node_output["messages"]:
                    if isinstance(msg, AIMessage):
                        if msg.content and not msg.tool_calls:
                            text = msg.content.strip()
                            if text:
                                last_plain_answer_parts.append(text)
                                print(f"{self.spec.log_prefix} [{node_name}] 思考/回复: {text}")
                        if msg.tool_calls:
                            for tc in msg.tool_calls:
                                print(
                                    f"🛠️ [{node_name}] 准备调用工具: {tc['name']}({tc['args']})"
                                )
                    elif isinstance(msg, ToolMessage):
                        content = msg.content
                        if len(str(content)) > 200:
                            content = str(content)[:200] + "...(截断)"
                        print(f"✅ [{node_name}] 工具结果: {content}")

        final_answer = "\n".join(part for part in last_plain_answer_parts if part)
        if final_answer:
            await asyncio.to_thread(
                self.memory_agent.process_interaction,
                user_input=user_input,
                agent_output=final_answer,
                source=self.spec.source,
            )
            await asyncio.to_thread(self.memory_agent.maintenance_tick)
        return final_answer

    async def run_interaction_turn(
        self,
        turn_prompt: str,
        *,
        interaction_thread_id: str,
        stream_to_stdout: bool = False,
    ) -> str:
        scoped_thread_id = f"{self.spec.thread_id}:{interaction_thread_id}"
        return await self.run_once(
            turn_prompt,
            stream_to_stdout=stream_to_stdout,
            conversation_thread_id=scoped_thread_id,
        )

    def _collect_plain_parts(self, event: dict, sink: list[str]) -> None:
        for node_output in event.values():
            if "messages" not in node_output:
                continue
            for msg in node_output["messages"]:
                if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
                    text = msg.content.strip()
                    if text:
                        sink.append(text)

    async def run_cli(self) -> None:
        await self.initialize()
        print(f"{self.spec.log_prefix} {self.spec.display_name} 已启动（输入 'exit' 或按 Ctrl+C 退出）")
        while True:
            try:
                user_input = input("\n用户：")
            except (EOFError, KeyboardInterrupt):
                break

            if not user_input or not user_input.strip():
                continue
            if user_input.lower().strip() == "exit":
                break

            print("-" * 50)
            await self.run_once(user_input, stream_to_stdout=True)
            print("-" * 50)


__all__ = ["AgentRuntime", "AgentSpec"]
