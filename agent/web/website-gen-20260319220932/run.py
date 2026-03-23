# -*- coding: utf-8 -*-
"""一键启动：同时启动前后端，生成可直接访问的网址。"""
import os
import subprocess
import sys
import time
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
os.chdir(WEB_DIR)

def main():
    print("正在一键启动网站...")
    procs = []
    try:
        # 启动后端
        if (WEB_DIR / "main.py").exists():
            p = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
                cwd=str(WEB_DIR),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
            )
            procs.append(("后端", p))
            time.sleep(1)
        # 启动前端
        if (WEB_DIR / "package.json").exists():
            cmd = "npm run dev"
            p = subprocess.Popen(
                cmd,
                cwd=str(WEB_DIR),
                shell=True,
            )
            procs.append(("前端", p))
            time.sleep(2)
        print()
        print("=" * 50)
        print("  一键启动完成！")
        print("  访问网址: http://127.0.0.1:3000")
        print("=" * 50)
        print("按 Ctrl+C 停止所有服务")
        for name, proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        for name, proc in procs:
            proc.terminate()
        print("\n已停止服务")

if __name__ == "__main__":
    main()
