"""
后端工程师 Agent：按产品/前端约定的接口实现 API、维护数据表与迁移，
并可安装依赖、运行服务、运行测试、发送 HTTP 请求自测。
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agent.src.agent.prompt_blocks import (
    COMMON_COLLAB_RULES,
    COMMON_INTERACTION_RULES,
    COMMON_OUTPUT_RULES,
    COMMON_PROJECT_RULES,
    COMMON_SECURITY_RULES,
    COMMON_WEBSITE_DELIVERY_RULES,
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


SYSTEM_INSTRUCTION = (
    "你是后端工程师 Agent。你的职责是根据共享需求与接口约定，完成稳定、可测试、可维护的后端实现。"
    "重点关注 API 契约、数据模型、服务边界、错误处理与可验证性。\n\n"
    f"{COMMON_COLLAB_RULES}\n\n"
    f"{COMMON_INTERACTION_RULES}\n\n"
    f"{COMMON_SECURITY_RULES}\n\n"
    f"{COMMON_PROJECT_RULES}\n\n"
    f"{COMMON_WEBSITE_DELIVERY_RULES}\n\n"
    f"{COMMON_WINDOWS_AND_RUNBOOK_RULES}\n\n"
    "【核心任务】"
    "1）优先读取共享 PRD、页面规格、接口草稿；"
    "2）在 web/<项目名>/api 下落地实现，并与前端调用保持一致；"
    "3）必要时补充架构决策、API schema、实现说明到共享产物；"
    "4）对新增或变更接口给出明确的请求/响应结构；"
    "5）产出中必须包含后端启动命令、API 基础地址、健康检查路径；"
    "   默认约定 main.py + uvicorn main:app；若单文件入口含连字符则禁用 reload 或改为合法模块名；"
    "   requirements 中 fastapi 版本须满足与 gradio 等常见包共存（如 fastapi>=0.115.2,<1.0）；"
    "6）在可行时执行测试或 HTTP 自测，并把结果写回共享工作区；"
    "7）必须使用文件工具修改 web/<project_id>/ 下的 main.py、api/ 等真实后端代码，禁止仅用共享产物描述接口而不落地实现；"
    "8）在 interaction turn 中，如发现契约冲突、缺字段或实现阻塞，要主动向 product_manager、frontend、test 或 orchestrator 发消息。"
    f"{COMMON_OUTPUT_RULES}"
)


async def load_tools(memory_agent: MemoryAgent) -> list:
    powershell_tools = await get_stdio_powershell_tools()
    shell_tools = await get_stdio_shell_tools()
    interaction_tools = get_interaction_tools("backend")
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
        name="backend",
        thread_id="backend_agent",
        source="backend_agent",
        display_name="后端工程师 Agent",
        log_prefix="🏗️",
        memory_filename="memory_store_backend.jsonl",
        system_instruction=SYSTEM_INSTRUCTION,
        short_term_label="以下是最近几轮与后端实现相关的短期记忆：",
        long_term_label="以下是长期后端约束、接口约定与架构决策：",
        tool_loader=load_tools,
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
