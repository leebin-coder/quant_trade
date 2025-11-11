#!/usr/bin/env python3
"""
量化交易系统主服务
持续运行，定时执行策略和监控市场
"""
import asyncio
import signal
import sys
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.utils.logger import logger
from app.core.config import settings
from app.tasks.stock_data_fetcher import StockDataFetcher
from app.tasks.trading_calendar_fetcher import TradingCalendarFetcher


class TradingService:
    """交易服务主类"""

    def __init__(self):
        self.running = False
        self.tasks = []
        self.stock_fetcher = StockDataFetcher()
        self.calendar_fetcher = TradingCalendarFetcher()
        self.scheduler = AsyncIOScheduler()
        logger.info(f"初始化 {settings.project_name} v{settings.version}")

    async def start(self):
        """启动服务"""
        self.running = True
        logger.info("=" * 60)
        logger.info(f"🚀 {settings.project_name} 服务启动")
        logger.info(f"📊 模拟模式: {settings.simulation_mode}")
        logger.info(f"🔄 交易启用: {settings.trading_enabled}")
        logger.info("=" * 60)

        # 注册信号处理
        self._setup_signal_handlers()

        # 启动各个任务
        self.tasks = [
            asyncio.create_task(self._market_monitor_loop()),
            asyncio.create_task(self._strategy_execution_loop()),
            asyncio.create_task(self._health_check_loop()),
            asyncio.create_task(self._stock_data_fetch_loop()),
            asyncio.create_task(self._company_data_fetch_loop()),
        ]

        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            logger.info("服务任务已取消")

    async def stop(self):
        """停止服务"""
        logger.info("正在停止服务...")
        self.running = False

        # 关闭调度器
        if self.scheduler.running:
            logger.info("正在关闭调度器...")
            self.scheduler.shutdown(wait=False)

        # 取消所有任务
        for task in self.tasks:
            task.cancel()

        # 等待任务完成
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("✅ 服务已安全停止")

    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备退出...")
            asyncio.create_task(self.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _market_monitor_loop(self):
        """市场监控循环 - 每分钟检查一次"""
        logger.info("📈 市场监控任务已启动")

        while self.running:
            try:
                # TODO: 实现市场数据获取和监控逻辑
                logger.debug(f"[市场监控] {datetime.now().strftime('%H:%M:%S')}")

                # 这里可以添加：
                # - 获取实时行情数据
                # - 检查市场状态
                # - 更新持仓信息

                await asyncio.sleep(60)  # 每60秒执行一次

            except asyncio.CancelledError:
                logger.info("市场监控任务已取消")
                break
            except Exception as e:
                logger.error(f"市场监控出错: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _strategy_execution_loop(self):
        """策略执行循环 - 每5分钟执行一次"""
        logger.info("🎯 策略执行任务已启动")

        while self.running:
            try:
                if settings.trading_enabled:
                    # TODO: 实现策略执行逻辑
                    logger.debug(f"[策略执行] {datetime.now().strftime('%H:%M:%S')}")

                    # 这里可以添加：
                    # - 运行交易策略
                    # - 生成交易信号
                    # - 执行交易指令
                else:
                    logger.debug("交易未启用，跳过策略执行")

                await asyncio.sleep(300)  # 每5分钟执行一次

            except asyncio.CancelledError:
                logger.info("策略执行任务已取消")
                break
            except Exception as e:
                logger.error(f"策略执行出错: {e}", exc_info=True)
                await asyncio.sleep(300)

    async def _health_check_loop(self):
        """健康检查循环 - 每30秒检查一次"""
        logger.info("💚 健康检查任务已启动")

        while self.running:
            try:
                # TODO: 实现健康检查逻辑
                status = {
                    "time": datetime.now().isoformat(),
                    "running": self.running,
                    "simulation_mode": settings.simulation_mode,
                    "trading_enabled": settings.trading_enabled,
                }
                logger.debug(f"[健康检查] 系统运行正常 - {status['time']}")

                await asyncio.sleep(30)  # 每30秒检查一次

            except asyncio.CancelledError:
                logger.info("健康检查任务已取消")
                break
            except Exception as e:
                logger.error(f"健康检查出错: {e}", exc_info=True)
                await asyncio.sleep(30)

    async def _stock_data_fetch_task(self):
        """股票数据获取任务 - 由调度器触发"""
        try:
            logger.info("触发定时股票数据同步任务...")
            await self.stock_fetcher.fetch_all_stock_info()
        except Exception as e:
            logger.error(f"股票数据获取出错: {e}", exc_info=True)

    async def _trading_calendar_fetch_task(self):
        """交易日历数据获取任务 - 由调度器触发"""
        try:
            logger.info("触发定时交易日历同步任务...")
            await self.calendar_fetcher.sync_trading_calendar()
        except Exception as e:
            logger.error(f"交易日历数据获取出错: {e}", exc_info=True)

    async def _stock_data_fetch_loop(self):
        """股票数据获取调度器 - 每天凌晨0:00执行"""
        logger.info("📊 股票数据获取任务调度器已启动")
        logger.info(f"⏰ 调度时间: 每天 {settings.stock_fetch_schedule_hour:02d}:{settings.stock_fetch_schedule_minute:02d}")

        # 配置 cron 触发器：每天凌晨0:00执行
        stock_trigger = CronTrigger(
            day_of_week=settings.stock_fetch_schedule_day_of_week,
            hour=settings.stock_fetch_schedule_hour,
            minute=settings.stock_fetch_schedule_minute
        )

        # 配置 cron 触发器：每周末凌晨1:00执行
        company_trigger = CronTrigger(
            day_of_week=settings.company_fetch_schedule_day_of_week,
            hour=settings.company_fetch_schedule_hour,
            minute=settings.company_fetch_schedule_minute
        )

        # 配置 cron 触发器：每天凌晨2:00执行
        calendar_trigger = CronTrigger(
            day_of_week=settings.trading_calendar_schedule_day_of_week,
            hour=settings.trading_calendar_schedule_hour,
            minute=settings.trading_calendar_schedule_minute
        )

        # 添加股票数据获取调度任务
        self.scheduler.add_job(
            self._stock_data_fetch_task,
            trigger=stock_trigger,
            id="stock_data_fetch",
            name="股票数据获取任务",
            replace_existing=True
        )
        logger.info("✓ 股票数据获取调度任务已添加")

        # 添加公司数据获取调度任务
        self.scheduler.add_job(
            self._company_data_fetch_task,
            trigger=company_trigger,
            id="company_data_fetch",
            name="公司数据获取任务",
            replace_existing=True
        )
        logger.info("🏢 公司数据获取任务调度器已启动")
        logger.info(f"⏰ 调度时间: 每周 {settings.company_fetch_schedule_day_of_week} {settings.company_fetch_schedule_hour:02d}:{settings.company_fetch_schedule_minute:02d}")
        logger.info("✓ 公司数据获取调度任务已添加")

        # 添加交易日历获取调度任务
        self.scheduler.add_job(
            self._trading_calendar_fetch_task,
            trigger=calendar_trigger,
            id="trading_calendar_fetch",
            name="交易日历获取任务",
            replace_existing=True
        )
        logger.info("📅 交易日历获取任务调度器已启动")
        logger.info(f"⏰ 调度时间: 每天 {settings.trading_calendar_schedule_hour:02d}:{settings.trading_calendar_schedule_minute:02d}")
        logger.info("✓ 交易日历获取调度任务已添加")

        # 启动调度器
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("=" * 60)
            logger.info("✓ APScheduler 调度器已启动")
            logger.info("等待定时任务触发...")
            logger.info("=" * 60)

        # 保持任务运行，等待取消
        try:
            while self.running:
                await asyncio.sleep(60)  # 每分钟检查一次运行状态
        except asyncio.CancelledError:
            logger.info("调度器已取消")
            if self.scheduler.running:
                self.scheduler.shutdown()
            raise

    async def _company_data_fetch_task(self):
        """公司数据获取任务 - 由调度器触发"""
        try:
            logger.info("触发定时公司数据同步任务...")
            await self.stock_fetcher.fetch_all_company_info()
        except Exception as e:
            logger.error(f"公司数据获取出错: {e}", exc_info=True)

    async def _company_data_fetch_loop(self):
        """公司数据获取调度器 - 已合并到 _stock_data_fetch_loop"""
        # 此方法已废弃，调度逻辑已合并到 _stock_data_fetch_loop
        logger.info("公司数据获取调度已在股票数据调度器中统一管理")

        # 保持任务运行，等待取消
        try:
            while self.running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.info("公司数据获取调度器循环已取消")
            raise


async def main():
    """主函数"""
    service = TradingService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断")
    except Exception as e:
        logger.error(f"服务异常: {e}", exc_info=True)
    finally:
        await service.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序退出")
        sys.exit(0)
