import sys

from agent.src.utilis.mcp import create_mcp_stdio_client


async def get_stdio_shell_tools():
    params = {
        "command": sys.executable,
        "args":[
            r"C:\Users\Administrator\Desktop\app\agent\src\mcp\shell_tools.py"
        ]
    }

    client, tools = await create_mcp_stdio_client("shell_tools", params)
    return tools