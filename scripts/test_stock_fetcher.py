#!/usr/bin/env python3
"""
测试股票数据获取功能
独立运行脚本，用于验证股票数据获取是否正常工作
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.tasks.stock_data_fetcher import StockDataFetcher
from app.utils.logger import logger


async def main():
    """测试主函数"""
    logger.info("=" * 80)
    logger.info("开始测试股票数据获取功能...")
    logger.info("=" * 80)

    fetcher = StockDataFetcher()

    try:
        # 直接执行获取任务（忽略时间检查）
        await fetcher.fetch_all_stock_info()

        logger.info("\n" + "=" * 80)
        logger.info("测试完成！")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"测试过程中出错: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("\n测试被用户中断")
        sys.exit(0)
