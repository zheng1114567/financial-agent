"""
前端工程师 Agent：负责页面与交互实现、仿站、静态资源与前端工程化。
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
    COMMON_UI_EXCELLENCE_RULES,
    COMMON_WEBSITE_DELIVERY_RULES,
    COMMON_WINDOWS_AND_RUNBOOK_RULES,
)
from agent.src.agent.runtime import AgentRuntime, AgentSpec
from agent.src.tool.collaboration_tools import get_collaboration_tools
from agent.src.tool.browser_tools import get_browser_tools
from agent.src.tool.file_tools import file_tools
from agent.src.tool.interaction_tools import get_interaction_tools
from agent.src.tool.memory_tools import MemoryAgent, get_memory_tools
from agent.src.tool.powershell_tools import get_stdio_powershell_tools
from agent.src.tool.shell_tools import get_stdio_shell_tools
import agent.src.tool.fetch_tools as fetch_tools_module


def _load_project_file(filepath: str, label: str, max_chars: int = 6000) -> str | None:
    """讀取指定檔案並做長度截斷，失敗時返回 None。"""
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n...（內容過長，已截斷）"
        return f"以下是當前網站的 {label} 檔案內容，修改時請以此為準：\n{content}"
    except Exception:
        # 不因讀檔失敗阻塞對話
        return None


def build_project_context_messages(project_hint: str | None = None) -> List[SystemMessage]:
    """為當前前端專案構建檔案上下文訊息。"""
    messages: List[SystemMessage] = []
    project = resolve_project_context(project_hint)
    if not project:
        return messages

    messages.append(
        SystemMessage(
            content="以下是当前解析到的项目上下文，请后续修改以前先以此为准：\n"
            + format_project_context_summary(project)
        )
    )

    candidate_files = project.html_files[:6] + project.css_files[:3] + project.js_files[:3]
    for filepath in candidate_files:
        label = os.path.relpath(filepath, os.path.dirname(project.web_dir)) if project.web_dir else filepath
        content = _load_project_file(filepath, label)
        if content:
            messages.append(SystemMessage(content=content))

    return messages


SYSTEM_INSTRUCTION = (
    "你是前端工程师 Agent。你的职责是根据共享需求与设计约束，完成页面、交互和前端工程化实现。"
    "你要产出的不是孤立 demo，而是能与后端协同工作的完整网站前端。\n\n"
    f"{COMMON_COLLAB_RULES}\n\n"
    f"{COMMON_INTERACTION_RULES}\n\n"
    f"{COMMON_SECURITY_RULES}\n\n"
    f"{COMMON_PROJECT_RULES}\n\n"
    f"{COMMON_WEBSITE_DELIVERY_RULES}\n\n"
    f"{COMMON_REFERENCE_SITE_RULES}\n\n"
    f"{COMMON_UI_EXCELLENCE_RULES}\n\n"
    f"{COMMON_WINDOWS_AND_RUNBOOK_RULES}\n\n"
    "【核心任务】"
    "1）优先读取 PRD、REFERENCE_FETCH_NOTES.md（若有）、页面结构、API 契约和现有项目文件；"
    "2）在已有网站基础上增量修改，保持风格与结构一致；"
    "3）若 PRD 含仿站/Design Tokens：严格按 token 与区块对照表实现；可用浏览器工具对照参考站做层级检查（不复制文案与素材）；"
    "4）确保导航入口、按钮行为、请求结构与真实 API 一致；"
    "5）产出中必须包含前端启动命令与默认访问网址；"
    "6）将页面规格、实现说明、风险点写入共享工作区；"
    "7）若页面包含多视图或多页结构，要明确入口与返回路径；"
    "8）必须使用文件工具读写 web/<project_id>/ 下的真实文件（如 src/、index.html、vite 配置）；"
    "禁止仅通过 write_shared_artifact 写说明而不改仓库内源码；与 orchestrator 注入的脚手架并存时须增量实现 PRD，勿删除 run.py/package.json 导致无法启动；"
    "9）在 interaction turn 中，若接口不明确或测试暴露问题，要主动向 product_manager、backend、test 或 orchestrator 发消息。"
    f"{COMMON_OUTPUT_RULES}"
)


async def load_tools(memory_agent: MemoryAgent) -> list:
    powershell_tools = await get_stdio_powershell_tools()
    shell_tools = await get_stdio_shell_tools()
    browser_tools = await get_browser_tools()
    fetch_tools = await fetch_tools_module.get_fetch_tools()
    interaction_tools = get_interaction_tools("frontend")
    return (
        powershell_tools
        + shell_tools
        + file_tools
        + browser_tools
        + fetch_tools
        + get_memory_tools(memory_agent)
        + get_collaboration_tools()
        + interaction_tools
    )


def build_spec() -> AgentSpec:
    return AgentSpec(
        name="frontend",
        thread_id="frontend_agent",
        source="frontend_agent",
        display_name="前端工程师 Agent",
        log_prefix="🎨",
        memory_filename="memory_store_frontend.jsonl",
        system_instruction=SYSTEM_INSTRUCTION,
        short_term_label="以下是最近几轮与前端实现相关的短期记忆：",
        long_term_label="以下是长期前端偏好、结构约束与设计决策：",
        tool_loader=load_tools,
        context_builder=lambda user_input: build_project_context_messages(
            guess_project_id_from_text(user_input)
        ),
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
