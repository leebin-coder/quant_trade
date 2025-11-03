#!/bin/bash
# 手动启动调度任务的快捷脚本

# 切换到项目根目录
cd "$(dirname "$0")"

# 运行任务脚本
python3 scripts/run_tasks.py
