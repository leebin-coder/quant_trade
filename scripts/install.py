#!/usr/bin/env python3
"""
依赖安装脚本
"""
import subprocess
import sys
import os


def run_command(cmd):
    """运行命令行命令"""
    try:
        result = subprocess.run(cmd, shell=True, check=True,
                                capture_output=True, text=True)
        print(f"✅ {cmd}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {cmd} 失败: {e}")
        return False


def main():
    """主安装函数"""
    env = sys.argv[1] if len(sys.argv) > 1 else "dev"

    print(f"🚀 安装量化交易系统 - {env} 环境")

    # 基础安装
    if env == "dev":
        if not run_command("pip install -e .[dev]"):
            sys.exit(1)
    elif env == "prod":
        if not run_command("pip install -e .[prod]"):
            sys.exit(1)
    else:
        if not run_command("pip install -e ."):
            sys.exit(1)

    print(f"🎉 {env} 环境安装完成！")


if __name__ == "__main__":
    main()