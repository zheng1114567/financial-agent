"""
测试工程师 Agent：负责根据 PRD 和接口契约设计/执行测试，输出测试报告，
帮助前端/后端工程师发现并定位问题，而不是直接实现业务功能。
"""
import asyncio
import os
import sys
from typing import List

from langchain_core.messages import SystemMessage

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.src.agent.project_context import (
    format_project_context_summary,
    guess_project_id_from_text,
    resolve_project_context,
)
from agent.src.agent.prompt_blocks import (
    COMMON_COLLAB_RULES,
    COMMON_INTERACTION_RULES,
    COMMON_OUTPUT_RULES,
    COMMON_PROJECT_RULES,
    COMMON_REFERENCE_SITE_RULES,
    COMMON_SECURITY_RULES,
    COMMON_WEBSITE_DELIVERY_RULES,
    COMMON_TEST_VERIFICATION_RULES,
    COMMON_WINDOWS_AND_RUNBOOK_RULES,
)
from agent.src.agent.runtime import AgentRuntime, AgentSpec
from agent.src.tool.collaboration_tools import get_collaboration_tools
from agent.src.tool.backend_tools import get_backend_tools
from agent.src.tool.file_tools import file_tools
from agent.src.tool.interaction_tools import get_interaction_tools
from agent.src.tool.memory_tools import MemoryAgent, get_memory_tools
from agent.src.tool.powershell_tools import get_stdio_powershell_tools
from agent.src.tool.shell_tools import get_stdio_shell_tools


def build_test_project_context_messages(project_hint: str | None = None) -> List[SystemMessage]:
    """注入 web 專案根路徑，避免測試 Agent 憑空拼錯路徑、從不調用 run_tests/request_http。"""
    messages: List[SystemMessage] = []
    project = resolve_project_context(project_hint)
    if not project:
        messages.append(
            SystemMessage(
                content=(
                    "【测试上下文】未能解析唯一 web 项目。"
                    "请从用户消息或协作任务中识别 project_id，"
                    "并对 agent/web/<project_id>/ 使用 get_project_tree 定位后再执行 run_tests / request_http。"
                )
            )
        )
        return messages

    messages.append(
        SystemMessage(
            content="【测试上下文】以下路径为当前网站项目根目录（run_tests、get_project_tree 等请优先使用 web_dir）：\n"
            + format_project_context_summary(project)
        )
    )
    if project.web_dir:
        messages.append(
            SystemMessage(
                content=(
                    f"【强制参数】run_tests 的 project_dir 请使用（原样复制）：\n{project.web_dir}\n"
                    "request_http 健康检查优先：http://127.0.0.1:8000/health\n"
                    "若 PRD 规定其他端口或路径，以 PRD 为准并说明偏差。"
                )
            )
        )
    return messages


SYSTEM_INSTRUCTION = (
    "你是测试工程师 Agent。你的职责是根据共享需求、接口契约和现有实现，设计并执行验证。"
    "你主要负责测试计划、缺陷报告、验收结论，不负责主业务实现。\n\n"
    f"{COMMON_COLLAB_RULES}\n\n"
    f"{COMMON_INTERACTION_RULES}\n\n"
    f"{COMMON_SECURITY_RULES}\n\n"
    f"{COMMON_PROJECT_RULES}\n\n"
    f"{COMMON_WEBSITE_DELIVERY_RULES}\n\n"
    f"{COMMON_REFERENCE_SITE_RULES}\n\n"
    f"{COMMON_WINDOWS_AND_RUNBOOK_RULES}\n\n"
    f"{COMMON_TEST_VERIFICATION_RULES}\n\n"
    "【核心任务】"
    "1）读取 PRD、接口文档、共享实现说明；若 PRD 含参考网址仿站要求，按契约检查 REFERENCE_FETCH_NOTES、区块对照表与 Design Tokens 是否落地；"
    "2）整理测试范围、关键用例、边界条件；"
    "3）必要时运行 pytest 或 HTTP 自测；"
    "4）将测试计划、缺陷、验收状态写回共享工作区；"
    "5）报告需明确重现步骤、期望、实际、影响范围；"
    "6）验证启动后核心网址/API 是否可访问，并给出通过或失败证据；"
    "7）在 interaction turn 中，如发现缺陷、覆盖空白或前置条件不满足，要主动向 product_manager、frontend、backend 或 orchestrator 发消息。"
    f"{COMMON_OUTPUT_RULES}"
)


async def load_tools(memory_agent: MemoryAgent) -> list:
    powershell_tools = await get_stdio_powershell_tools()
    shell_tools = await get_stdio_shell_tools()
    interaction_tools = get_interaction_tools("test")
    return (
        powershell_tools
        + shell_tools
        + file_tools
        + get_backend_tools()
        + get_memory_tools(memory_agent)
        + get_collaboration_tools()
        + interaction_tools
    )


def build_spec() -> AgentSpec:
    return AgentSpec(
        name="test",
        thread_id="test_agent",
        source="test_agent",
        display_name="测试工程师 Agent",
        log_prefix="🧪",
        memory_filename="memory_store_test.jsonl",
        system_instruction=SYSTEM_INSTRUCTION,
        short_term_label="以下是最近几轮与测试验证相关的短期记忆：",
        long_term_label="以下是长期测试策略、历史缺陷与验收约束：",
        tool_loader=load_tools,
        context_builder=lambda user_input: build_test_project_context_messages(
            guess_project_id_from_text(user_input)
        ),
        use_llm_scoring=True,
    )


_RUNTIME: AgentRuntime | None = None


def get_runtime() -> AgentRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = AgentRuntime(build_spec())
    return _RUNTIME


async def run_agent():
    await get_runtime().run_cli()


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except Exception as e:
        print(f"运行出错: {e}")
        import traceback

        traceback.print_exc()

