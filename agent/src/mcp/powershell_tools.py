import subprocess
import time
import psutil
import os
import sys
import re
import pyautogui
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

mcp = FastMCP()

# 记录由本工具打开的 PowerShell 进程 PID，避免误杀 VS Code 集成终端等其他 PowerShell
OPENED_POWERSHELL_PIDS: set[int] = set()
def run_powershell_command(
    command: str,
    capture_output: bool = True,
    *,
    timeout: float | None = None,
):
    """执行 PowerShell 命令并返回 (stdout, stderr, returncode)。timeout 秒超时避免常驻进程卡死调用方。"""
    try:
        # 优先使用环境变量中的 PowerShell，可兼容 PowerShell 7 (pwsh)
        powershell_exe = os.environ.get("POWERSHELL_EXE", "powershell.exe")
        cmd = [powershell_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]

        if capture_output:
            # 不使用 shell=True，直接调用 powershell 可执行文件，避免在某些环境下命令被错误解析
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=False,
                timeout=timeout,
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        else:
            result = subprocess.run(cmd, shell=False, timeout=timeout)
            return "", "", result.returncode
    except subprocess.TimeoutExpired:
        return (
            "",
            (
                f"命令执行超过 {timeout} 秒已中断。"
                "若你在启动常驻服务（如 python uvicorn / backend-sse-server），"
                "不要用「python xxx.py | Out-File」这种管道——会一直阻塞。"
                "请改用：Start-Process python -ArgumentList '脚本路径' -WorkingDirectory '目录' -WindowStyle Hidden"
            ),
            124,
        )
    except FileNotFoundError as e:
        return "", f"找不到 PowerShell 可执行文件: {e}", 1
    except Exception as e:
        return "", str(e), 1


# 疑似「管道 + 常驻 Python 服务」会导致 subprocess 永远等不到 EOF
_LONG_RUNNING_PIPELINE_PATTERN = re.compile(
    r"\|\s*Out-File|\|\s*Tee-Object",
    re.IGNORECASE,
)
_LONG_RUNNING_SERVER_PATTERN = re.compile(
    r"(uvicorn|hypercorn|gunicorn|flask\s+run|backend-sse-server|sse-server\.py)",
    re.IGNORECASE,
)


def _looks_like_blocking_server_pipeline(script: str) -> bool:
    s = script.strip()
    if not _LONG_RUNNING_PIPELINE_PATTERN.search(s):
        return False
    return bool(_LONG_RUNNING_SERVER_PATTERN.search(s)) or "python" in s.lower()


def get_powershell_processes():
    """获取所有 PowerShell 进程"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = (proc.info['name'] or '').lower()
            # 同时兼容 Windows PowerShell 和 PowerShell 7 (pwsh)
            if 'powershell' in name or name.startswith('pwsh'):
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': proc.info['cmdline']
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return processes


def activate_powershell_window():
    """激活 PowerShell 窗口"""
    try:
        # 设置 pyautogui 的安全设置
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.1

        # 优先通过窗口标题查找 PowerShell 窗口
        windows = pyautogui.getWindowsWithTitle('Windows PowerShell')
        if not windows:
            windows = pyautogui.getWindowsWithTitle('PowerShell')
        if not windows:
            # 部分 PowerShell 7 或终端可能只显示 pwsh
            windows = pyautogui.getWindowsWithTitle('pwsh')

        if windows:
            # 激活第一个找到的 PowerShell 窗口
            window = windows[0]
            window.activate()
            time.sleep(0.5)  # 等待窗口激活
            return True
        else:
            # 如果没找到窗口，尝试通过快捷键
            pyautogui.hotkey('alt', 'tab')
            time.sleep(0.5)
            return False
    except Exception as e:
        print(f"激活 PowerShell 窗口失败: {e}")
        return False


@mcp.tool(name="get_powershell_processes", description="获取所有 PowerShell 进程信息")
def get_all_powershell_processes() -> str:
    """获取所有正在运行的 PowerShell 进程列表"""
    try:
        processes = get_powershell_processes()
        if not processes:
            return "当前没有运行的 PowerShell 进程"

        result = "PowerShell 进程列表:\n"
        for proc in processes:
            result += f"PID: {proc['pid']}, 名称: {proc['name']}\n"
        return result
    except Exception as e:
        return f"获取 PowerShell 进程失败: {str(e)}"


@mcp.tool(name="close_powershell", description="关闭所有 PowerShell 进程")
def close_all_powershell() -> str:
    """关闭由本工具打开的 PowerShell 进程，避免误关 IDE 集成终端等其他进程"""
    try:
        global OPENED_POWERSHELL_PIDS

        if not OPENED_POWERSHELL_PIDS:
            return "没有记录到需要关闭的 PowerShell 进程（只会关闭由本工具打开的窗口）"

        closed_count = 0
        failed_count = 0

        # 拷贝一份，避免遍历时修改集合
        pids_to_close = list(OPENED_POWERSHELL_PIDS)

        for pid in pids_to_close:
            try:
                proc = psutil.Process(pid)
                proc.terminate()
                closed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                failed_count += 1
            finally:
                # 无论成功失败，都从记录中移除，避免下次重复尝试
                OPENED_POWERSHELL_PIDS.discard(pid)

        return (
            f"已尝试关闭由本工具打开的 PowerShell 进程：成功 {closed_count} 个，失败 {failed_count} 个"
        )
    except Exception as e:
        return f"关闭 PowerShell 进程失败: {str(e)}"


@mcp.tool(name="open_powershell", description="打开新的 PowerShell 窗口（用于需要可视化终端时，普通命令建议优先使用非交互式工具）")
def open_new_powershell(
    working_directory: Annotated[
        str,
        Field(description="可选的工作目录，为空则使用当前目录"),
    ] = "",
) -> str:
    """打开新的 PowerShell 窗口（并记录由本工具启动的 PowerShell PID）"""
    try:
        # 使用 -PassThru 拿到新进程 PID，方便之后只关闭自己开的窗口
        if working_directory and os.path.exists(working_directory):
            command = (
                'Start-Process powershell '
                f'-WorkingDirectory "{working_directory}" '
                '-PassThru | Select-Object -ExpandProperty Id'
            )
        else:
            command = (
                'Start-Process powershell '
                '-PassThru | Select-Object -ExpandProperty Id'
            )

        stdout, stderr, return_code = run_powershell_command(command, capture_output=True)

        if return_code != 0 and stderr:
            return f"打开 PowerShell 失败: {stderr}"

        # 解析 PID 并记录下来
        try:
            pid_str = (stdout or "").strip()
            if pid_str:
                pid = int(pid_str)
                OPENED_POWERSHELL_PIDS.add(pid)
        except Exception:
            # 解析失败不影响主流程，只是无法精确记录 PID
            pass

        time.sleep(2)  # 等待窗口打开
        processes = get_powershell_processes()
        return (
            f"PowerShell 已打开，当前运行进程数: {len(processes)}；"
            f"由本工具记录的窗口数: {len(OPENED_POWERSHELL_PIDS)}"
        )
    except Exception as e:
        return f"打开 PowerShell 失败: {str(e)}"


def _is_dangerous_powershell_script(script: str) -> str | None:
    """
    基於簡單黑名單的 PowerShell 高危命令檢查。
    返回命中規則的描述，未命中則返回 None。
    """
    lower = script.lower().strip()

    dangerous_substrings = [
        # 保留真正高風險的磁碟 / 系統級操作
        "format-volume",
        "format ",
        "diskpart",
        "clear-disk",
        "clean-disk",
        "shutdown",
        "restart-computer",
    ]

    for pattern in dangerous_substrings:
        if pattern in lower:
            return pattern

    return None


@mcp.tool(
    name="run_powershell_script",
    description=(
        "通过 pyautogui 向前台 PowerShell 窗口发送命令，用于需要在可见终端中交互的场景。"
        "普通腳本（例如刪除資料夾）推薦優先使用 run_powershell_noninteractive。"
    ),
)
def run_powershell_script(
    script: Annotated[
        str,
        Field(description="要在 PowerShell 窗口中执行的脚本命令"),
    ]
) -> str:
    """通过 pyautogui 向活动的 PowerShell 窗口发送命令（帶高危命令防護）"""
    try:
        hit = _is_dangerous_powershell_script(script)
        if hit is not None:
            return f"安全策略：检测到高危 PowerShell 命令片段 `{hit}`，已拒绝发送。"

        # 检查是否有 PowerShell 进程在运行
        processes = get_powershell_processes()
        if not processes:
            return "没有找到运行中的 PowerShell 进程，请先打开 PowerShell 窗口"

        # 激活 PowerShell 窗口
        if not activate_powershell_window():
            return "无法激活 PowerShell 窗口，请确保 PowerShell 窗口已打开"

        # 清空当前输入行（如果有的话）
        pyautogui.hotkey('ctrl', 'c')  # 取消当前命令
        time.sleep(0.2)

        # 确保光标在命令行
        pyautogui.press('end')
        time.sleep(0.1)

        # 输入命令
        pyautogui.write(script, interval=0.02)
        time.sleep(0.3)

        # 按 Enter 执行命令
        pyautogui.press('enter')

        return f"命令已发送到 PowerShell 窗口: {script}"

    except Exception as e:
        return f"发送 PowerShell 命令失败: {str(e)}"


@mcp.tool(
    name="run_powershell_noninteractive",
    description=(
        "在後台直接執行一段 PowerShell 腳本，不依賴 GUI 窗口。"
        "適合文件操作、批量處理；預設最長等待 120 秒，超時會自動中斷以免卡死。"
        "禁止：用「python 某伺服器.py | Out-File」啟動常駐服務——管道會永遠阻塞。"
        "常駐服務請用：Start-Process python -ArgumentList '路徑\\腳本.py' -WorkingDirectory '目錄' -WindowStyle Hidden"
    ),
)
def run_powershell_noninteractive(
    script: Annotated[
        str,
        Field(description="要执行的完整 PowerShell 脚本内容"),
    ],
    timeout_seconds: Annotated[
        int,
        Field(
            description="最长等待秒数，默认 120；纯查询可改小，合法长任务可改大（仍不建议用管道挂起常驻进程）",
            ge=5,
            le=3600,
        ),
    ] = 120,
) -> str:
    """
    直接通過 powershell.exe / pwsh 執行腳本，返回 stdout/stderr。
    相比 run_powershell_script，不需要前台窗口，更穩定。
    """
    try:
        hit = _is_dangerous_powershell_script(script)
        if hit is not None:
            return f"安全策略：检测到高危 PowerShell 命令片段 `{hit}`，已拒绝执行。"

        if _looks_like_blocking_server_pipeline(script):
            return (
                "已拒绝执行：检测到「管道重定向（| Out-File 等）+ 疑似 Python/伺服器」组合。"
                "常駐进程不会结束，会导致本工具一直卡住。"
                "请改用（示例）："
                "Start-Process python -ArgumentList 'backend-sse-server.py' "
                "-WorkingDirectory 'C:\\\\path\\\\to\\\\src\\\\lib' -WindowStyle Hidden"
            )

        # 使用已有的 run_powershell_command 幫助函數執行腳本
        # 這裡直接將腳本文本傳給 -Command
        # 注意：由於是後台執行，Write-Host 等輸出會收集到 stdout 中返回
        command = script
        stdout, stderr, return_code = run_powershell_command(
            command,
            capture_output=True,
            timeout=float(timeout_seconds),
        )
        if return_code != 0 and stderr:
            return f"执行失败（退出码 {return_code}）：\n{stderr}"
        if return_code == 124:
            return stderr or "执行超时。"
        return stdout or "脚本已执行完成（无输出）。"
    except Exception as e:
        return f"执行 PowerShell 脚本失败: {str(e)}"


if __name__ == "__main__":
    try:
        mcp.run(transport="stdio")
    except Exception as e:
        raise
