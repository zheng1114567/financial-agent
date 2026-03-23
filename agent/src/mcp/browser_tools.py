import time
from mcp.server.fastmcp import FastMCP
import requests

mcp = FastMCP()


@mcp.tool(
    name="fetch_webpage_html",
    description="拉取指定網址的 HTML，用於分析並生成類似風格的靜態頁面",
)
def fetch_webpage_html(url: str) -> str:
    """
    使用 HTTP 請求抓取指定 URL 的原始 HTML。
    - 不依賴瀏覽器或 Selenium，在服務器環境下也可穩定工作。
    - 出於上下文長度考量，對返回的 HTML 做適度截斷（例如前 15000 字符）。
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        html = resp.text
        max_len = 15000
        if len(html) > max_len:
            html = html[:max_len] + "\n<!-- HTML 已截斷，僅保留前 15000 字符供分析使用 -->"
        return html
    except Exception as e:
        return f"抓取網頁失敗: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")