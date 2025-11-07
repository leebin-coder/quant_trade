#!/usr/bin/env python3
"""
测试公司信息同步功能
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.tasks.stock_data_fetcher import StockDataFetcher
from app.utils.logger import logger


async def test_company_sync():
    """测试公司信息同步"""
    logger.info("=" * 80)
    logger.info("测试公司信息同步功能")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    fetcher = StockDataFetcher()

    try:
        await fetcher.fetch_all_company_info()
        logger.info("\n✅ 测试成功！")
    except Exception as e:
        logger.error(f"\n❌ 测试失败: {e}", exc_info=True)
        return False

    return True


if __name__ == "__main__":
    try:
        start_time = datetime.now()
        success = asyncio.run(test_company_sync())
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if success:
            logger.info(f"\n⏱️  任务执行耗时: {duration:.2f} 秒")
        else:
            logger.error(f"\n⏱️  任务执行失败，耗时: {duration:.2f} 秒")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程序异常退出: {e}", exc_info=True)
        sys.exit(1)
