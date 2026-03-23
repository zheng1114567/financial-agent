import sys

from agent.src.utilis.mcp import create_mcp_stdio_client


async def get_stdio_powershell_tools():
    params = {
        # 使用当前运行 Agent 的解释器，避免不同环境导致依赖缺失
        "command": sys.executable,
        "args": [
            r"C:\Users\Administrator\Desktop\app\agent\src\mcp\powershell_tools.py"
        ],
    }

    client, tools = await create_mcp_stdio_client("powershell_tools", params)
    return tools