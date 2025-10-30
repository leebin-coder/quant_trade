#!/usr/bin/env python3
"""
服务管理脚本
用于启动、停止、重启量化交易服务
"""
import os
import sys
import signal
import subprocess
import time
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
PID_FILE = PROJECT_ROOT / "quant_trade.pid"
LOG_FILE = PROJECT_ROOT / "logs" / "service.log"


def is_running():
    """检查服务是否运行"""
    if not PID_FILE.exists():
        return False

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        # 检查进程是否存在
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        # 进程不存在或PID文件损坏
        PID_FILE.unlink(missing_ok=True)
        return False


def start():
    """启动服务"""
    if is_running():
        print("❌ 服务已在运行中")
        return 1

    print("🚀 正在启动量化交易服务...")

    # 确保日志目录存在
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 启动服务
    process = subprocess.Popen(
        [sys.executable, "-m", "app.main"],
        cwd=PROJECT_ROOT,
        stdout=open(LOG_FILE, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # 保存PID
    with open(PID_FILE, "w") as f:
        f.write(str(process.pid))

    # 等待一下，确认服务启动成功
    time.sleep(2)

    if is_running():
        print(f"✅ 服务启动成功 (PID: {process.pid})")
        print(f"📋 日志文件: {LOG_FILE}")
        return 0
    else:
        print("❌ 服务启动失败，请查看日志")
        return 1


def stop():
    """停止服务"""
    if not is_running():
        print("⚠️  服务未运行")
        return 0

    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())

        print(f"🛑 正在停止服务 (PID: {pid})...")

        # 发送 SIGTERM 信号
        os.kill(pid, signal.SIGTERM)

        # 等待进程退出
        for _ in range(30):  # 最多等待30秒
            time.sleep(1)
            if not is_running():
                break
        else:
            # 超时，强制杀死
            print("⚠️  正常停止超时，强制终止...")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

        PID_FILE.unlink(missing_ok=True)
        print("✅ 服务已停止")
        return 0

    except Exception as e:
        print(f"❌ 停止服务失败: {e}")
        return 1


def restart():
    """重启服务"""
    print("🔄 正在重启服务...")
    stop()
    time.sleep(2)
    return start()


def status():
    """查看服务状态"""
    if is_running():
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        print(f"✅ 服务正在运行 (PID: {pid})")
        return 0
    else:
        print("❌ 服务未运行")
        return 1


def logs():
    """查看日志"""
    if not LOG_FILE.exists():
        print("❌ 日志文件不存在")
        return 1

    print(f"📋 日志文件: {LOG_FILE}")
    print("=" * 60)

    # 显示最后50行日志
    try:
        subprocess.run(["tail", "-n", "50", "-f", str(LOG_FILE)])
    except KeyboardInterrupt:
        print("\n日志查看已停止")

    return 0


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python service_manager.py {start|stop|restart|status|logs}")
        return 1

    command = sys.argv[1].lower()

    commands = {
        "start": start,
        "stop": stop,
        "restart": restart,
        "status": status,
        "logs": logs,
    }

    if command not in commands:
        print(f"❌ 未知命令: {command}")
        print("可用命令: start, stop, restart, status, logs")
        return 1

    return commands[command]()


if __name__ == "__main__":
    sys.exit(main())
