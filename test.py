# validate_config.py
import os
import sys

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

print("=== 配置验证 ===")

try:
    # 重新导入配置模块以确保使用最新代码
    import importlib
    from app.core import config

    importlib.reload(config)

    from app.core.config import settings

    print("✅ 配置加载成功!")
    print(f"项目名称: {settings.project_name}")
    print(f"版本: {settings.version}")
    print(f"API地址: {settings.api_host}:{settings.api_port}")
    print(f"数据库URL: {settings.database_url}")
    print(f"模拟模式: {settings.simulation_mode}")
    print(f"交易启用: {settings.trading_enabled}")

    print("\n✅ 所有配置验证通过!")

except Exception as e:
    print(f"❌ 配置错误: {e}")
    import traceback

    traceback.print_exc()