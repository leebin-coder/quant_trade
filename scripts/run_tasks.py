#!/usr/bin/env python3
"""
手动启动调度任务脚本
提供所有调度任务的手动执行入口
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.tasks.stock_data_fetcher import StockDataFetcher
from app.tasks.trading_calendar_fetcher import TradingCalendarFetcher
from app.tasks.stock_daily_fetcher import StockDailyFetcher
from app.utils.logger import logger


class TaskRunner:
    """任务运行器"""

    def __init__(self):
        self.stock_fetcher = StockDataFetcher()
        self.calendar_fetcher = TradingCalendarFetcher()
        self.daily_fetcher = StockDailyFetcher()

    async def run_stock_sync(self):
        """
        运行股票基本信息同步任务
        同步A股股票基本信息到数据库
        """
        logger.info("=" * 80)
        logger.info("手动执行：股票基本信息同步任务")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            await self.stock_fetcher.fetch_all_stock_info()
            logger.info("\n✅ 股票基本信息同步任务执行成功！")
        except Exception as e:
            logger.error(f"\n❌ 股票基本信息同步任务执行失败: {e}", exc_info=True)
            return False

        return True

    async def run_company_sync(self):
        """
        运行公司信息同步任务
        从 Tushare Pro 获取全量公司基本信息并同步到数据库
        """
        logger.info("=" * 80)
        logger.info("手动执行：公司信息同步任务")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            await self.stock_fetcher.fetch_all_company_info()
            logger.info("\n✅ 公司信息同步任务执行成功！")
        except Exception as e:
            logger.error(f"\n❌ 公司信息同步任务执行失败: {e}", exc_info=True)
            return False

        return True

    async def run_trading_calendar_sync(self):
        """
        运行交易日历同步任务
        从 Baostock 获取交易日历并同步到数据库
        """
        logger.info("=" * 80)
        logger.info("手动执行：交易日历同步任务")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            await self.calendar_fetcher.sync_trading_calendar()
            logger.info("\n✅ 交易日历同步任务执行成功！")
        except Exception as e:
            logger.error(f"\n❌ 交易日历同步任务执行失败: {e}", exc_info=True)
            return False

        return True

    async def run_stock_daily_sync(self):
        """
        运行股票日线数据同步任务
        从 Baostock 获取日线数据（3种复权类型）并同步到数据库
        """
        logger.info("=" * 80)
        logger.info("手动执行：股票日线数据同步任务")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            await self.daily_fetcher.sync_stock_daily()
            logger.info("\n✅ 股票日线数据同步任务执行成功！")
        except Exception as e:
            logger.error(f"\n❌ 股票日线数据同步任务执行失败: {e}", exc_info=True)
            return False

        return True


def print_menu():
    """打印菜单"""
    print("\n" + "=" * 60)
    print("📋 调度任务手动执行菜单")
    print("=" * 60)
    print("1. 执行股票基本信息同步任务")
    print("   - 从数据源获取A股股票列表")
    print("   - 比对数据库，插入新股票")
    print()
    print("2. 执行公司信息同步任务")
    print("   - 从 Tushare Pro 获取全量公司基本信息")
    print("   - 批量插入/更新到数据库")
    print()
    print("3. 执行交易日历同步任务")
    print("   - 从 Baostock 获取交易日历数据")
    print("   - 智能判断并增量更新")
    print()
    print("4. 执行股票日线数据同步任务")
    print("   - 从 Baostock 获取日线数据")
    print("   - 遍历所有股票，获取3种复权类型数据")
    print("   - 批量插入数据库（1000条/批）")
    print()
    print("0. 退出")
    print("=" * 60)


async def main():
    """主函数"""
    runner = TaskRunner()

    while True:
        print_menu()
        choice = input("请选择要执行的任务 (0-4): ").strip()

        if choice == "0":
            logger.info("退出任务运行器")
            break
        elif choice == "1":
            confirm = input("\n确认执行股票基本信息同步任务？(y/n): ").strip().lower()
            if confirm == "y":
                start_time = datetime.now()
                success = await runner.run_stock_sync()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                if success:
                    logger.info(f"\n⏱️  任务执行耗时: {duration:.2f} 秒")
                else:
                    logger.error(f"\n⏱️  任务执行失败，耗时: {duration:.2f} 秒")
            else:
                logger.info("取消执行")
        elif choice == "2":
            confirm = input("\n确认执行公司信息同步任务？(y/n): ").strip().lower()
            if confirm == "y":
                start_time = datetime.now()
                success = await runner.run_company_sync()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                if success:
                    logger.info(f"\n⏱️  任务执行耗时: {duration:.2f} 秒")
                else:
                    logger.error(f"\n⏱️  任务执行失败，耗时: {duration:.2f} 秒")
            else:
                logger.info("取消执行")
        elif choice == "3":
            confirm = input("\n确认执行交易日历同步任务？(y/n): ").strip().lower()
            if confirm == "y":
                start_time = datetime.now()
                success = await runner.run_trading_calendar_sync()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                if success:
                    logger.info(f"\n⏱️  任务执行耗时: {duration:.2f} 秒")
                else:
                    logger.error(f"\n⏱️  任务执行失败，耗时: {duration:.2f} 秒")
            else:
                logger.info("取消执行")
        elif choice == "4":
            confirm = input("\n确认执行股票日线数据同步任务？(y/n): ").strip().lower()
            if confirm == "y":
                start_time = datetime.now()
                success = await runner.run_stock_daily_sync()
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                if success:
                    logger.info(f"\n⏱️  任务执行耗时: {duration:.2f} 秒")
                else:
                    logger.error(f"\n⏱️  任务执行失败，耗时: {duration:.2f} 秒")
            else:
                logger.info("取消执行")
        else:
            print("❌ 无效的选择，请重新输入")

        input("\n按回车键继续...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"\n程序异常退出: {e}", exc_info=True)
        sys.exit(1)
