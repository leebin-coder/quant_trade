#!/usr/bin/env python3
"""
开发环境设置脚本
"""
import subprocess
import sys


def setup_development_environment():
    """设置开发环境"""
    commands = [
        "pip install -e .[dev]",  # 安装开发依赖
        "pre-commit install",  # 安装 git hooks
        "python scripts/init_database.py",  # 初始化数据库
    ]

    for cmd in commands:
        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"✅ {cmd}")
        except subprocess.CalledProcessError:
            print(f"❌ {cmd} 失败")
            sys.exit(1)

    print("🎉 开发环境设置完成！")


if __name__ == "__main__":
    setup_development_environment()