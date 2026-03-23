from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_fetch_tools():
    """
    從遠端 MCP 服務獲取 fetch 類工具，用於將 HTML 轉為 Markdown / 提取內容等。
    """
    client = MultiServerMCPClient(
        {
            "fetch": {
                "transport": "http",
                "url": "https://mcp.api-inference.modelscope.net/f664173aa6624b/mcp",
            }
        }
    )

    tools = await client.get_tools()
    return tools


__all__ = ["get_fetch_tools"]
