import sys

from agent.src.utilis.mcp import create_mcp_stdio_client
from mcp.server.fastmcp import FastMCP

mcp = FastMCP()


async def get_browser_tools():
    params = {
        # 使用当前運行 Agent 的直譯器，避免不同環境導致依賴缺失
        "command": sys.executable,
        "args": [
            r"C:\Users\Administrator\Desktop\app\agent\src\mcp\browser_tools.py"
        ],
    }

    client, tools = await create_mcp_stdio_client("browser_tools", params)
    return tools