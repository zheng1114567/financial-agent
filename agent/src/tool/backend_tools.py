"""
后端工程师 Agent 专用工具：项目树、代码搜索、运行测试、HTTP 请求。
"""
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

# 默认排除的目录名（不进入、不列出）
DEFAULT_EXCLUDE_DIRS = {
    "__pycache__",
    "node_modules",
    ".git",
    ".venv",
    "venv",
    ".idea",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}


def _tree_string(
    path: Path,
    prefix: str = "",
    max_depth: int = 6,
    current_depth: int = 0,
    exclude_dirs: Optional[set] = None,
) -> str:
    if current_depth >= max_depth:
        return ""
    exclude_dirs = exclude_dirs or DEFAULT_EXCLUDE_DIRS
    lines = []
    try:
        entries = sorted(path.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
    except PermissionError:
        return f"{prefix}(无权限)\n"
    dirs = [e for e in entries if e.is_dir() and e.name not in exclude_dirs]
    files = [e for e in entries if e.is_file()]
    for i, entry in enumerate(dirs):
        is_last_dir = i == len(dirs) - 1 and len(files) == 0
        connector = "└── " if is_last_dir else "├── "
        lines.append(prefix + connector + entry.name + "/")
        next_prefix = prefix + ("    " if is_last_dir else "│   ")
        sub = _tree_string(
            entry,
            prefix=next_prefix,
            max_depth=max_depth,
            current_depth=current_depth + 1,
            exclude_dirs=exclude_dirs,
        )
        if sub:
            lines.append(sub)
    for i, entry in enumerate(files):
        is_last = i == len(files) - 1
        connector = "└── " if is_last else "├── "
        lines.append(prefix + connector + entry.name)
    return "\n".join(lines) if lines else ""


@tool("get_project_tree")
def get_project_tree(
    root_dir: str,
    max_depth: int = 6,
) -> str:
    """
    获取项目目录树，便于快速了解项目结构。
    root_dir: 项目根目录的绝对路径或相对于当前工作目录的路径。
    max_depth: 最大层级深度，默认 6。会排除 __pycache__、node_modules、.git 等目录。
    """
    root = Path(root_dir).resolve()
    if not root.exists():
        return f"路径不存在: {root_dir}"
    if not root.is_dir():
        return f"不是目录: {root_dir}"
    return root.name + "/\n" + _tree_string(root, max_depth=max_depth)


@tool("search_in_files")
def search_in_files(
    directory: str,
    pattern: str,
    file_glob: str = "*.py",
    max_results: int = 50,
) -> str:
    """
    在指定目录下按关键词或正则搜索文件内容，返回匹配的文件路径与行内容。
    directory: 要搜索的目录绝对路径。
    pattern: 搜索关键词或正则表达式（普通字符串会按字面匹配）。
    file_glob: 文件名通配符，默认 *.py；设为 * 可搜索所有文件。
    max_results: 最多返回的匹配行数，默认 50。
    """
    root = Path(directory).resolve()
    if not root.exists() or not root.is_dir():
        return f"目录不存在或无效: {directory}"
    try:
        re.compile(pattern)
        use_regex = True
    except re.error:
        use_regex = False
    results = []
    count = 0
    for path in root.rglob(file_glob):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        rel_path = path.relative_to(root)
        for line_no, line in enumerate(text.splitlines(), 1):
            if count >= max_results:
                break
            if use_regex:
                if re.search(pattern, line):
                    results.append(f"{rel_path}:{line_no}: {line.strip()[:200]}")
                    count += 1
            else:
                if pattern in line:
                    results.append(f"{rel_path}:{line_no}: {line.strip()[:200]}")
                    count += 1
        if count >= max_results:
            break
    if not results:
        return f"在 {directory} 下未找到匹配 \"{pattern}\" 的内容（file_glob={file_glob}）。"
    return "\n".join(results)


@tool("run_tests")
def run_tests(
    project_dir: str,
    extra_args: str = "",
) -> str:
    """
    在指定项目目录下执行 pytest，返回完整输出。
    project_dir: 项目根目录（含 tests 或测试文件的目录）。
    extra_args: 额外参数，如 \"-v\" 或 \"-k test_login\"，默认为空。
    """
    project_path = Path(project_dir).resolve()
    if not project_path.exists() or not project_path.is_dir():
        return f"项目目录不存在或无效: {project_dir}"
    cmd = [os.environ.get("PYTHON", "python"), "-m", "pytest"]
    if extra_args.strip():
        cmd.extend(extra_args.strip().split())
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = result.stdout or ""
        err = result.stderr or ""
        combined = (out + "\n" + err).strip()
        return f"退出码: {result.returncode}\n\n{combined}"
    except subprocess.TimeoutExpired:
        return "测试执行超时（120 秒）。"
    except FileNotFoundError:
        return "未找到 pytest，请确保已安装 pytest（pip install pytest）。"
    except Exception as e:
        return f"执行测试时出错: {e}"


@tool("request_http")
def request_http(
    url: str,
    method: str = "GET",
    body: str = "",
    headers_json: str = "",
) -> str:
    """
    向指定 URL 发送 HTTP 请求，返回状态码和响应体。用于自测接口是否按约定返回。
    url: 完整 URL，如 http://127.0.0.1:8000/api/health
    method: 请求方法，GET 或 POST，默认 GET。
    body: 请求体（POST 时使用），纯文本或 JSON 字符串。
    headers_json: 可选，JSON 格式的请求头，如 {\"Content-Type\": \"application/json\"}
    """
    try:
        import urllib.request
        import json as _json
    except ImportError:
        return "当前环境无法使用 urllib，请安装标准库或使用 requests。"
    method = method.upper() or "GET"
    req_headers = {}
    if headers_json.strip():
        try:
            req_headers = _json.loads(headers_json)
        except _json.JSONDecodeError:
            return f"headers_json 不是合法 JSON: {headers_json}"
    if body and "Content-Type" not in req_headers and method == "POST":
        req_headers["Content-Type"] = "application/json"
    data = body.encode("utf-8") if body and method == "POST" else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.getcode()
            resp_body = resp.read().decode("utf-8", errors="replace")
            return f"状态码: {status}\n\n响应体:\n{resp_body[:4000]}"
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            body = ""
        return f"HTTP 错误: {e.code} {e.reason}\n\n{body}"
    except urllib.error.URLError as e:
        return f"请求失败: {e.reason}"
    except Exception as e:
        return f"请求出错: {e}"


def get_backend_tools():
    """返回后端工程师 Agent 使用的工具列表。"""
    return [
        get_project_tree,
        search_in_files,
        run_tests,
        request_http,
    ]


__all__ = ["get_backend_tools", "get_project_tree", "search_in_files", "run_tests", "request_http"]
