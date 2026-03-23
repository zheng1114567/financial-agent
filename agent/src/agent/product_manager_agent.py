"""
产品经理 Agent：负责理解业务需求、拆解功能、产出 PRD / 接口契约草稿，
为前端工程师与后端工程师提供清晰的一致性规范。
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
    COMMON_REFERENCE_SITE_RULES,
    COMMON_REFERENCE_URL_FUNCTION_RULES,
    COMMON_SECURITY_RULES,
    COMMON_WEBSITE_DELIVERY_RULES,
    COMMON_WINDOWS_AND_RUNBOOK_RULES,
)
from agent.src.agent.runtime import AgentRuntime, AgentSpec
from agent.src.tool.collaboration_tools import get_collaboration_tools
from agent.src.tool.file_tools import file_tools
from agent.src.tool.interaction_tools import get_interaction_tools
from agent.src.tool.memory_tools import MemoryAgent, get_memory_tools
import agent.src.tool.fetch_tools as fetch_tools_module


SYSTEM_INSTRUCTION = (
    "你是产品经理 Agent。你的职责是把用户目标转成前后端可执行的结构化需求。"
    "你只负责产品定义、页面结构、功能拆解、接口契约与协作约束，不负责直接写业务实现代码。\n\n"
    f"{COMMON_COLLAB_RULES}\n\n"
    f"{COMMON_INTERACTION_RULES}\n\n"
    f"{COMMON_SECURITY_RULES}\n\n"
    f"{COMMON_PROJECT_RULES}\n\n"
    f"{COMMON_WEBSITE_DELIVERY_RULES}\n\n"
    f"{COMMON_REFERENCE_SITE_RULES}\n\n"
    f"{COMMON_REFERENCE_URL_FUNCTION_RULES}\n\n"
    f"{COMMON_WINDOWS_AND_RUNBOOK_RULES}\n\n"
    "【核心任务】"
    "1）基于用户目标定义角色、页面、核心流程、功能列表、验收标准；"
    "2）在共享工作区写入 PRD、页面地图、API 契约草稿；"
    "3）当用户给出参考网址时：必须先工具抓取并写入 docs/REFERENCE_FETCH_NOTES.md（含「功能与交互线索」小节），"
    "再在 PRD.md 写仿站分析、页面区块对照表、功能对标矩阵、Design Tokens；"
    "   禁止只写「参考某 URL」一句话敷衍；禁止只做视觉描述不写可交付功能；禁止复制原站品牌与原创文案；"
    "4）输出必须足够清晰，让前端知道要做哪些页面，让后端知道要实现哪些接口；"
    "5）PRD 最少包含：目标用户、核心场景、用户目标与范围收敛（Must/Should/Won't）、用户故事与验收映射、页面地图、页面级功能点、"
    "功能对标矩阵（有 URL 时）、数据实体与关键字段、接口清单（逐条含错误码与空状态）、字段契约、可执行验收检查项、启动说明；"
    "   有参考网址时还必须包含：仿站分析、区块对照表、功能对标矩阵、Design Tokens；"
    "   最终 PRD 必须固定输出到 web/<project>/docs/PRD.md；"
    "   禁止保留模板占位句或「待补充」；每个页面至少写清：入口 URL/路由、主要组件、加载/空/错/成功四种状态、依赖的 API；"
    "6）PRD 的「启动说明」须可照做即成功：包含 PowerShell 下的 .\\ 前缀、前后端端口、依赖安装命令，并与实际目录结构一致；"
    "7）在 interaction turn 中，如果需求不完整或方案需要确认，要主动给 frontend、backend、test 或 orchestrator 发消息。"
    f"{COMMON_OUTPUT_RULES}"
)


async def load_tools(memory_agent: MemoryAgent) -> list:
    fetch_tools = await fetch_tools_module.get_fetch_tools()
    interaction_tools = get_interaction_tools("product_manager")
    return (
        file_tools
        + fetch_tools
        + get_memory_tools(memory_agent)
        + get_collaboration_tools()
        + interaction_tools
    )


def build_spec() -> AgentSpec:
    return AgentSpec(
        name="product_manager",
        thread_id="product_manager_agent",
        source="product_manager_agent",
        display_name="产品经理 Agent",
        log_prefix="📋",
        memory_filename="memory_store_pm.jsonl",
        system_instruction=SYSTEM_INSTRUCTION,
        short_term_label="以下是最近几轮与需求梳理相关的短期记忆：",
        long_term_label="以下是项目长期偏好、约束与既有产品决策：",
        tool_loader=load_tools,
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

