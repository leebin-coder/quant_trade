"""
实时Tick数据获取任务
每天9:00-15:30运行，获取实时行情数据
"""
import asyncio
from datetime import datetime, time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
import time as time_module

import tushare as ts
import httpx

from app.core.config import settings
from app.utils.logger import logger


class RealtimeTickFetcher:
    """实时Tick数据获取器"""

    def __init__(self):
        """初始化"""
        self.api_base_url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.stock_api_token}"
        }
        # 初始化 tushare pro
        self.tushare_token = "347ae3b92b9a97638f155512bc599767558b94c3dcb47f5abd058b95"
        ts.set_token(self.tushare_token)
        self.pro = ts.pro_api()

        # 配置参数
        self.batch_size = 50  # sina数据源一次最多获取50只股票
        self.max_workers = 5  # 线程池大小，每个线程处理50只股票
        self.fetch_interval = 3  # 每次获取间隔（秒）

    async def get_all_stocks_except_bse(self) -> List[str]:
        """
        获取除北交所外的所有股票代码

        Returns:
            List[str]: 股票代码列表（格式：000001.SZ）
        """
        try:
            logger.info("正在从后端API获取所有股票...")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/stocks/all",
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    data = result.get("data", {})

                    # data可能是list或dict，需要兼容处理
                    if isinstance(data, list):
                        stocks = data
                    elif isinstance(data, dict):
                        stocks = data.get("records", [])
                    else:
                        stocks = []

                    # 过滤掉北交所（BSE）的股票
                    stock_codes = [
                        stock["stockCode"]
                        for stock in stocks
                        if stock.get("exchange") != "BSE"
                    ]

                    logger.info(f"成功获取 {len(stock_codes)} 只股票（已排除北交所）")
                    return stock_codes
                else:
                    logger.error(f"获取股票列表失败: {result.get('message')}")
                    return []

        except Exception as e:
            logger.error(f"获取股票列表异常: {e}", exc_info=True)
            return []

    def fetch_realtime_tick_batch(self, stock_codes: List[str]) -> Optional[List[Dict]]:
        """
        获取一批股票的实时tick数据（同步方法，供线程池使用）

        Args:
            stock_codes: 股票代码列表（最多50只）

        Returns:
            Optional[List[Dict]]: tick数据列表
        """
        try:
            # 将股票代码列表转换为逗号分隔的字符串
            ts_codes = ",".join(stock_codes)

            logger.info(f"正在获取 {len(stock_codes)} 只股票的实时数据: {stock_codes[:3]}...")

            # 调用tushare实时行情接口
            df = ts.realtime_quote(ts_code=ts_codes, src='sina')

            if df is None or df.empty:
                logger.warning(f"未获取到数据: {stock_codes[:3]}")
                return None

            # 转换为字典列表，保留所有字段
            tick_data_list = []
            for _, row in df.iterrows():
                # 将整行数据转换为字典
                tick_data = row.to_dict()
                tick_data_list.append(tick_data)

            logger.info(f"成功获取 {len(tick_data_list)} 条实时数据")
            return tick_data_list

        except Exception as e:
            logger.error(f"获取实时数据失败: {e}", exc_info=True)
            return None

    async def fetch_realtime_tick_test(self):
        """
        测试版本：仅获取601398.SH的实时tick数据
        每隔1秒请求一次，持续打印到控制台
        按Ctrl+C停止
        """
        logger.info("=" * 80)
        logger.info("开始测试实时Tick数据获取（仅601398.SH）...")
        logger.info("每隔1秒请求一次，按Ctrl+C停止")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        test_stock = "601398.SH"
        request_count = 0

        try:
            # 在线程池中执行同步的tushare调用
            loop = asyncio.get_event_loop()

            # 持续循环获取数据
            while True:
                request_count += 1
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                logger.info(f"\n{'='*80}")
                logger.info(f"第 {request_count} 次请求 - {current_time}")
                logger.info(f"{'='*80}")

                with ThreadPoolExecutor(max_workers=1) as executor:
                    tick_data_list = await loop.run_in_executor(
                        executor,
                        self.fetch_realtime_tick_batch,
                        [test_stock]
                    )

                if tick_data_list:
                    for tick_data in tick_data_list:
                        # 打印所有字段
                        logger.info(f"\n【{tick_data.get('TS_CODE', 'N/A')} - {tick_data.get('NAME', 'N/A')}】实时数据：")
                        logger.info("-" * 80)

                        # 按类别打印所有字段
                        for key, value in sorted(tick_data.items()):
                            logger.info(f"{key:15} = {value}")

                        logger.info("=" * 80)
                else:
                    logger.warning("⚠️  本次未获取到tick数据")

                # 等待1秒后继续下一次请求
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info(f"\n\n{'='*80}")
            logger.info(f"用户中断，共完成 {request_count} 次请求")
            logger.info(f"{'='*80}")
        except Exception as e:
            logger.error(f"实时Tick数据获取测试失败: {e}", exc_info=True)
            raise

    def fetch_realtime_tick_batch_once(self, stock_codes: List[str], batch_id: int, round_num: int):
        """
        获取一批股票的实时tick数据（执行一次，供同步调用）

        Args:
            stock_codes: 股票代码列表（最多50只）
            batch_id: 批次ID
            round_num: 轮次号
        """
        try:
            current_time = datetime.now().strftime('%H:%M:%S')

            # 调用tushare实时行情接口
            ts_codes = ",".join(stock_codes)
            df = ts.realtime_quote(ts_code=ts_codes, src='sina')

            if df is None or df.empty:
                logger.warning(f"[批次{batch_id:>3}] 第{round_num:>3}次 {current_time} - 未获取到数据")
            else:
                # 转换为字典列表，保留所有字段
                tick_data_list = []
                for _, row in df.iterrows():
                    tick_data = row.to_dict()
                    tick_data_list.append(tick_data)

                # 只打印第一条数据的完整字段
                if tick_data_list:
                    first_tick = tick_data_list[0]
                    # 将所有字段格式化为字符串
                    fields_str = " | ".join([f"{k}:{v}" for k, v in sorted(first_tick.items())])
                    print(f"[批次{batch_id:>3}] 第{round_num:>3}次 ({len(tick_data_list)}只) | {fields_str}")

                # TODO: 这里调用入库接口
                # await self.save_tick_data_to_db(tick_data_list)

        except Exception as e:
            logger.error(f"[批次{batch_id}] 第{round_num}次 - 获取数据失败: {e}")

    def fetch_realtime_tick_batch_loop(self, stock_codes: List[str], batch_id: int, stop_event):
        """
        持续获取一批股票的实时tick数据（同步方法，供线程池使用）
        每隔3秒请求一次

        Args:
            stock_codes: 股票代码列表（最多50只）
            batch_id: 批次ID
            stop_event: 停止事件
        """
        request_count = 0

        while not stop_event.is_set():
            try:
                request_count += 1
                current_time = datetime.now().strftime('%H:%M:%S')

                # 调用tushare实时行情接口
                ts_codes = ",".join(stock_codes)
                df = ts.realtime_quote(ts_code=ts_codes, src='sina')

                if df is None or df.empty:
                    logger.warning(f"[批次{batch_id:>3}] 第{request_count:>3}次 {current_time} - 未获取到数据")
                else:
                    # 转换为字典列表，保留所有字段
                    tick_data_list = []
                    for _, row in df.iterrows():
                        tick_data = row.to_dict()
                        tick_data_list.append(tick_data)

                    # 提取时间和股票代码
                    times_and_codes = []
                    for tick_data in tick_data_list:
                        ts_code = tick_data.get('TS_CODE', 'N/A')
                        tick_time = tick_data.get('TIME', 'N/A')
                        times_and_codes.append(f"{tick_time}|{ts_code}")

                    # 打印表格样式（一行显示批次、次数和所有股票的时间|代码）
                    print(f"[批次{batch_id:>3}] 第{request_count:>3}次 | {' '.join(times_and_codes)}")

                    # TODO: 这里调用入库接口
                    # await self.save_tick_data_to_db(tick_data_list)

            except Exception as e:
                logger.error(f"[批次{batch_id}] 第{request_count}次 {current_time} - 获取数据失败: {e}")

            # 等待3秒后继续下一次请求
            if not stop_event.is_set():
                time_module.sleep(3)

        logger.info(f"[批次{batch_id}] 线程停止，共完成 {request_count} 次请求")

    async def check_is_trading_day(self, date_str: str = None) -> bool:
        """
        检查指定日期是否为交易日

        Args:
            date_str: 日期字符串，格式：YYYY-MM-DD，默认为今天

        Returns:
            bool: 是否为交易日
        """
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        try:
            logger.info(f"正在检查 {date_str} 是否为交易日...")

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/trading-calendar/is-trading-day",
                    headers=self.headers,
                    params={"date": date_str}
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    data = result.get("data", {})
                    is_trading_day = data.get("isTradingDay", False)
                    logger.info(f"{date_str} {'是' if is_trading_day else '不是'}交易日")
                    return is_trading_day
                else:
                    logger.error(f"检查交易日失败: {result.get('message')}")
                    return False

        except Exception as e:
            logger.error(f"检查交易日异常: {e}", exc_info=True)
            return False

    async def start_realtime_tick_sync(self):
        """
        启动实时tick数据同步任务
        前提条件：今天是交易日
        运行时间：9:00-15:30
        按50只股票分组，所有批次同时发起请求，严格3秒一轮
        """
        logger.info("=" * 80)
        logger.info("启动实时Tick数据同步任务...")
        logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        # 1. 检查今天是否为交易日
        today = datetime.now().strftime('%Y-%m-%d')
        is_trading_day = await self.check_is_trading_day(today)

        if not is_trading_day:
            logger.warning(f"今天 {today} 不是交易日，任务不执行")
            return

        # 2. 检查当前时间是否在交易时间内
        current_time = datetime.now().time()
        morning_start = time(9, 0)      # 上午9:00
        morning_end = time(11, 30)      # 上午11:30
        afternoon_start = time(13, 0)   # 下午13:00
        afternoon_end = time(15, 30)    # 下午15:30

        in_morning_session = morning_start <= current_time <= morning_end
        in_afternoon_session = afternoon_start <= current_time <= afternoon_end

        if not (in_morning_session or in_afternoon_session):
            logger.warning(f"当前时间 {current_time} 不在交易时间内（9:00-11:30 或 13:00-15:30），任务不执行")
            return

        try:
            # 3. 获取所有股票（除北交所）
            logger.info("\n步骤3: 获取所有股票列表（除北交所）...")
            all_stocks = await self.get_all_stocks_except_bse()

            if not all_stocks:
                logger.error("未获取到股票列表，任务终止")
                return

            logger.info(f"共需要处理 {len(all_stocks)} 只股票")

            # 4. 按50只股票分组
            batches = [
                all_stocks[i:i + self.batch_size]
                for i in range(0, len(all_stocks), self.batch_size)
            ]

            logger.info(f"共分为 {len(batches)} 组，每组最多{self.batch_size}只股票")
            logger.info(f"所有批次同时发起请求，严格3秒一轮，不等待慢批次")
            logger.info("按Ctrl+C停止所有线程")
            logger.info("=" * 80)

            # 5. 创建长期运行的线程池
            executor = ThreadPoolExecutor(max_workers=len(batches))
            request_count = 0

            try:
                while True:
                    # 检查当前时间是否在交易时段内
                    now_time = datetime.now().time()
                    in_morning = time(9, 0) <= now_time <= time(11, 30)
                    in_afternoon = time(13, 0) <= now_time <= time(15, 30)

                    # 如果不在交易时段，暂停执行
                    if not (in_morning or in_afternoon):
                        # 判断当前处于什么阶段
                        if now_time < time(9, 0):
                            logger.info(f"当前时间 {now_time} 未到开盘时间，等待至9:00...")
                            await asyncio.sleep(60)  # 等待1分钟后重新检查
                            continue
                        elif time(11, 30) < now_time < time(13, 0):
                            logger.info(f"当前时间 {now_time} 为午休时间，暂停执行，等待至13:00...")
                            await asyncio.sleep(60)  # 等待1分钟后重新检查
                            continue
                        elif now_time > time(15, 30):
                            logger.info(f"当前时间 {now_time} 已过收盘时间，任务结束")
                            break  # 结束任务
                        else:
                            await asyncio.sleep(10)  # 其他情况等待10秒
                            continue

                    request_count += 1
                    round_start_time = time_module.time()
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    logger.info(f"\n[第{request_count}轮请求] {current_time}")

                    # 所有批次同时发起请求（不等待结果）
                    futures = []
                    for batch_id, batch in enumerate(batches, start=1):
                        future = executor.submit(
                            self.fetch_realtime_tick_batch_once,
                            batch,
                            batch_id,
                            request_count
                        )
                        futures.append(future)

                    # 计算已用时间
                    elapsed = time_module.time() - round_start_time

                    # 严格保证3秒一轮（不等待所有批次完成）
                    sleep_time = max(0, 3 - elapsed)

                    if sleep_time > 0:
                        await asyncio.sleep(sleep_time)
                    else:
                        logger.warning(f"警告：发起请求耗时 {elapsed:.2f}秒，超过3秒间隔")

            except KeyboardInterrupt:
                logger.info("\n\n收到停止信号，正在关闭线程池...")
                executor.shutdown(wait=False)  # 不等待未完成的任务
                logger.info(f"共完成 {request_count} 轮请求")

            logger.info(f"\n✅ 实时Tick数据同步任务结束")

        except Exception as e:
            logger.error(f"实时Tick数据同步失败: {e}", exc_info=True)
            raise
