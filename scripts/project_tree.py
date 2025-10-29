import os
import fnmatch
from pathlib import Path


def should_ignore(path, ignore_patterns):
    """检查路径是否应该被忽略"""
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(path, pattern):
            return True
    return False


def print_tree(start_path, ignore_patterns=None, max_depth=None, current_depth=0, prefix=""):
    """递归打印目录树结构"""
    if ignore_patterns is None:
        ignore_patterns = [
            "__pycache__", "*.pyc", "*.pyo", "*.pyd",
            ".git", ".vscode", ".idea", "__pycache__",
            "*.egg-info", ".pytest_cache", "*.so", "*.dll",
            "node_modules", "*.log", "*.tmp", ".DS_Store",
            "*.sqlite3", "*.db", "venv", "env", ".env",
            "dist", "build", "*.egg", ".coverage", "htmlcov"
        ]

    if max_depth is not None and current_depth > max_depth:
        return

    try:
        items = sorted(os.listdir(start_path))
    except PermissionError:
        return

    # 过滤掉应该忽略的项目
    items = [item for item in items if not should_ignore(item, ignore_patterns)]

    for i, item in enumerate(items):
        item_path = os.path.join(start_path, item)
        is_last = i == len(items) - 1

        # 当前项的显示前缀
        connector = "└── " if is_last else "├── "
        print(prefix + connector + item)

        # 如果是目录，递归打印其内容
        if os.path.isdir(item_path):
            extension = "    " if is_last else "│   "
            print_tree(item_path, ignore_patterns, max_depth, current_depth + 1, prefix + extension)


def get_project_structure(start_dir=".", max_depth=None, output_file=None):
    """获取项目结构并打印或保存到文件"""
    start_path = os.path.abspath(start_dir)
    project_name = os.path.basename(start_path)

    print(f"项目结构: {project_name}/")
    print(".")

    if output_file:
        original_stdout = sys.stdout
        with open(output_file, 'w', encoding='utf-8') as f:
            sys.stdout = f
            print(f"项目结构: {project_name}/")
            print(".")
            print_tree(start_path, max_depth=max_depth)
            sys.stdout = original_stdout
        print(f"项目结构已保存到: {output_file}")
    else:
        print_tree(start_path, max_depth=max_depth)


if __name__ == "__main__":
    import sys

    # 解析命令行参数
    import argparse

    parser = argparse.ArgumentParser(description="输出项目目录结构")
    parser.add_argument("path", nargs="?", default=".", help="项目路径 (默认: 当前目录)")
    parser.add_argument("-d", "--depth", type=int, help="最大深度")
    parser.add_argument("-o", "--output", help="输出到文件")

    args = parser.parse_args()

    # 检查路径是否存在
    if not os.path.exists(args.path):
        print(f"错误: 路径 '{args.path}' 不存在")
        sys.exit(1)

    get_project_structure(args.path, args.depth, args.output)