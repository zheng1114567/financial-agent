import subprocess
import shlex
from pydantic import Field

from mcp.server.fastmcp import FastMCP
from typing import Annotated

mcp = FastMCP()


def _is_dangerous_shell_command(command: str) -> str | None:
    """
    基於簡單黑名單的高危命令檢查，防止誤執行破壞性操作。
    返回命中規則的描述，未命中則返回 None。
    """
    lower = command.lower().strip()

    # 通用高危關鍵字（適用於類 Unix / Windows）
    dangerous_substrings = [
        "rm -rf /",
        "rm -rf",
        "rm -r /",
        "mkfs",
        "mkfs.",
        "dd if=",
        ">:",
        ":(){:|:&};:",  # fork bomb
        "shutdown",
        "reboot",
        "poweroff",
        "format ",
        "diskpart",
    ]

    # Windows 專用極高風險命令（刪盤 / 分區管理等）；
    # 普通的 del / rmdir 不在這裡阻擋，因為經常用於正常開發操作。
    windows_dangerous = []

    for pattern in dangerous_substrings + windows_dangerous:
        if pattern in lower:
            return pattern

    return None


def _get_shell_timeout(command: str) -> int:
    """
    依命令類型決定超時秒數，避免查詢類命令在 Windows 上因 pip 延遲而長時間卡住。
    """
    lower = command.strip().lower()
    if lower.startswith("pip install") or lower.startswith("pip3 install"):
        return 300
    # 僅查詢、不裝包：pip show / pip list / python -c / --version 等，給短超時
    if any(lower.startswith(p) for p in ("pip show", "pip3 show", "pip list", "pip3 list")):
        return 20
    if lower.startswith("python ") and ("-c " in lower or "--version" in lower):
        return 20
    return 60


@mcp.tool(
    name="run_shell",
    description=(
        "run shell command（已啟用安全限制，禁止執行高危破壞性命令；"
        "LLM 在調用前必須先向用戶說明要執行的命令並獲得明確同意）"
    ),
)
def run_shell_command(command: Annotated[str, Field(description="shell commend will be executed")]) -> str:
    try:
        hit = _is_dangerous_shell_command(command)
        if hit is not None:
            return f"安全策略：檢測到高危命令片段 `{hit}`，已拒絕執行。"

        timeout_seconds = _get_shell_timeout(command)

        res = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        if res.returncode != 0:
            return res.stderr or res.stdout or f"exit code {res.returncode}"
        return res.stdout
    except subprocess.TimeoutExpired:
        return (
            f"命令執行超時（{timeout_seconds} 秒）。請在終端手動執行：\n{command}\n"
            "完成後可繼續讓 Agent 進行後續步驟。"
        )
    except Exception as e:
        return str(e)


def run_shell_commend_by_popen(command: str):
    res = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=True,
    )
    stdout, stderr = res.communicate()
    if stdout:
        return stdout
    return stderr


if __name__ == "__main__":
    mcp.run(transport="stdio")