"""
实时Tick数据获取任务
在交易日的 9:15-9:25、9:30-11:30、13:00-15:00 运行，获取实时行情数据
"""
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, time, date
from typing import Any, Dict, List, Optional, Tuple
import time as time_module

import httpx
import tushare as ts
from clickhouse_driver import Client

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
        self._auth_params = {"token": settings.stock_api_token}
        # 初始化 tushare pro
        self.tushare_token = "347ae3b92b9a97638f155512bc599767558b94c3dcb47f5abd058b95"
        ts.set_token(self.tushare_token)
        self.pro = ts.pro_api()

        # 配置参数
        self.batch_size = 50  # sina数据源一次最多获取50只股票
        self.max_workers = 5  # 线程池大小，每个线程处理50只股票
        self.fetch_interval = 3  # 每次获取间隔（秒）
        self.clickhouse_table = "market_realtime_ticks"
        self._clickhouse_local = threading.local()
        self.source_name = "tushare_realtime_quote"
        self.trading_windows = [
            (time(9, 15), time(9, 25)),
            (time(9, 30), time(11, 30)),
            (time(13, 0), time(15, 0)),
        ]
        self.clickhouse_columns = [
            "ts_code", "name",
            "trade", "price", "open", "high", "low", "pre_close",
            "bid", "ask", "volume", "amount",
            "b1_v", "b1_p", "b2_v", "b2_p", "b3_v", "b3_p", "b4_v", "b4_p", "b5_v", "b5_p",
            "a1_v", "a1_p", "a2_v", "a2_p", "a3_v", "a3_p", "a4_v", "a4_p", "a5_v", "a5_p",
            "date", "time", "source", "raw_json"
        ]
        self.clickhouse_insert_settings = {
            "async_insert": 1,
            "wait_for_async_insert": 0
        }

    def _with_token(self, extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(self._auth_params)
        if extra_params:
            params.update(extra_params)
        return params

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
                    headers=self.headers,
                    params=self._with_token()
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

    def _get_clickhouse_client(self) -> Client:
        """获取线程独立的 ClickHouse 客户端"""
        if not hasattr(self._clickhouse_local, "client"):
            self._clickhouse_local.client = Client(
                host=settings.clickhouse_host,
                port=settings.clickhouse_port,
                user=settings.clickhouse_user,
                password=settings.clickhouse_password,
                database=settings.clickhouse_database,
                settings={"strings_as_bytes": False},
            )
        return self._clickhouse_local.client

    @staticmethod
    def _extract_first_value(data: Dict, keys: List[str]):
        """从数据字典中按顺序提取第一个有效字段"""
        for key in keys:
            if key in data:
                value = data.get(key)
                if value not in (None, "", "--", "-"):
                    return value
        return None

    @staticmethod
    def _normalize_string(value) -> Optional[str]:
        """处理字符串字段"""
        if value in (None, "", "--", "-"):
            return None
        result = str(value).strip()
        return result or None

    @staticmethod
    def _parse_float(value) -> Optional[float]:
        """安全地将数据转换为浮点数"""
        if value in (None, "", "--", "-"):
            return None
        try:
            if isinstance(value, str):
                cleaned = value.replace(",", "").strip()
                if cleaned == "":
                    return None
                return float(cleaned)
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_trade_datetime(date_str: Optional[str], time_str: Optional[str]) -> Tuple[date, datetime]:
        """解析交易日期和时间"""
        fallback = datetime.now()

        parsed_date = None
        if date_str:
            cleaned = date_str.strip().replace("/", "-")
            if len(cleaned) == 8 and cleaned.isdigit():
                cleaned = f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:]}"
            for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
                try:
                    parsed_date = datetime.strptime(cleaned, fmt).date()
                    break
                except ValueError:
                    continue
        if parsed_date is None:
            parsed_date = fallback.date()

        parsed_time = None
        if time_str:
            cleaned_time = time_str.strip().replace(".", ":")
            for fmt in ("%H:%M:%S", "%H%M%S"):
                try:
                    parsed_time = datetime.strptime(cleaned_time, fmt).time()
                    break
                except ValueError:
                    continue

        if parsed_time is None:
            parsed_time = fallback.time()

        combined = datetime.combine(parsed_date, parsed_time)
        return parsed_date, combined
    def _get_trading_window_status(self, current_time: time) -> Tuple[str, Optional[time]]:
        """
        判断当前时间所处的实时tick采集窗口状态

        Returns:
            Tuple[str, Optional[time]]:
                - status: "active" 当前在采集窗口内；"upcoming" 尚未开始；"finished" 今日全部结束
                - reference_time: 当 status 为 "upcoming" 时表示下一窗口开始时间
        """
        for start, end in self.trading_windows:
            if start <= current_time <= end:
                return "active", end

        for start, _ in self.trading_windows:
            if current_time < start:
                return "upcoming", start

        return "finished", None

    def _build_tick_row(self, tick_data: Dict) -> Optional[Tuple]:
        """将 tick 字典转换为 ClickHouse 行，字段名与 Tushare 文档保持一致"""
        field_aliases = {
            "ts_code": ["ts_code", "TS_CODE"],
            "name": ["name", "NAME", "sec_name", "SECNAME"],
            "trade": ["trade", "TRADE"],
            "price": ["price", "PRICE"],
            "open": ["open", "OPEN"],
            "high": ["high", "HIGH"],
            "low": ["low", "LOW"],
            "pre_close": ["pre_close", "PRE_CLOSE", "preclose"],
            "bid": ["bid", "BID", "b1_p", "B1_P"],
            "ask": ["ask", "ASK", "a1_p", "A1_P"],
            "volume": ["volume", "VOLUME", "vol", "VOL"],
            "amount": ["amount", "AMOUNT", "turnover", "TURNOVER"],
            "b1_v": ["b1_v", "B1_V"],
            "b1_p": ["b1_p", "B1_P"],
            "b2_v": ["b2_v", "B2_V"],
            "b2_p": ["b2_p", "B2_P"],
            "b3_v": ["b3_v", "B3_V"],
            "b3_p": ["b3_p", "B3_P"],
            "b4_v": ["b4_v", "B4_V"],
            "b4_p": ["b4_p", "B4_P"],
            "b5_v": ["b5_v", "B5_V"],
            "b5_p": ["b5_p", "B5_P"],
            "a1_v": ["a1_v", "A1_V"],
            "a1_p": ["a1_p", "A1_P"],
            "a2_v": ["a2_v", "A2_V"],
            "a2_p": ["a2_p", "A2_P"],
            "a3_v": ["a3_v", "A3_V"],
            "a3_p": ["a3_p", "A3_P"],
            "a4_v": ["a4_v", "A4_V"],
            "a4_p": ["a4_p", "A4_P"],
            "a5_v": ["a5_v", "A5_V"],
            "a5_p": ["a5_p", "A5_P"],
            "date": ["date", "DATE"],
            "time": ["time", "TIME"],
        }

        ts_code = self._normalize_string(
            self._extract_first_value(tick_data, field_aliases["ts_code"])
        )
        if not ts_code:
            logger.debug("跳过一条缺少股票代码的tick数据")
            return None

        str_fields = {}
        str_fields["name"] = self._normalize_string(
            self._extract_first_value(tick_data, field_aliases["name"])
        )

        float_fields = {}
        numeric_keys = [
            "trade", "price", "open", "high", "low", "pre_close",
            "bid", "ask", "volume", "amount",
            "b1_v", "b1_p", "b2_v", "b2_p", "b3_v", "b3_p", "b4_v", "b4_p", "b5_v", "b5_p",
            "a1_v", "a1_p", "a2_v", "a2_p", "a3_v", "a3_p", "a4_v", "a4_p", "a5_v", "a5_p",
        ]
        for key in numeric_keys:
            float_fields[key] = self._parse_float(
                self._extract_first_value(tick_data, field_aliases.get(key, []))
            )

        date_raw = self._extract_first_value(tick_data, field_aliases["date"])
        time_raw = self._extract_first_value(tick_data, field_aliases["time"])
        trade_date, trade_datetime = self._parse_trade_datetime(
            date_raw, time_raw
        )

        row = (
            ts_code,
            str_fields.get("name") or ts_code,
            float_fields["trade"],
            float_fields["price"],
            float_fields["open"],
            float_fields["high"],
            float_fields["low"],
            float_fields["pre_close"],
            float_fields["bid"],
            float_fields["ask"],
            float_fields["volume"],
            float_fields["amount"],
            float_fields["b1_v"],
            float_fields["b1_p"],
            float_fields["b2_v"],
            float_fields["b2_p"],
            float_fields["b3_v"],
            float_fields["b3_p"],
            float_fields["b4_v"],
            float_fields["b4_p"],
            float_fields["b5_v"],
            float_fields["b5_p"],
            float_fields["a1_v"],
            float_fields["a1_p"],
            float_fields["a2_v"],
            float_fields["a2_p"],
            float_fields["a3_v"],
            float_fields["a3_p"],
            float_fields["a4_v"],
            float_fields["a4_p"],
            float_fields["a5_v"],
            float_fields["a5_p"],
            trade_date,
            trade_datetime,
            self.source_name,
            json.dumps(tick_data, ensure_ascii=False),
        )
        return row

    def save_tick_data_to_clickhouse(self, tick_data_list: List[Dict]):
        """将tick数据批量写入ClickHouse"""
        if not tick_data_list:
            return

        rows = []
        for tick_data in tick_data_list:
            row = self._build_tick_row(tick_data)
            if row:
                rows.append(row)

        if not rows:
            return

        try:
            client = self._get_clickhouse_client()
            columns_sql = ", ".join(self.clickhouse_columns)
            client.execute(
                f"INSERT INTO {self.clickhouse_table} ({columns_sql}) VALUES",
                rows,
                settings=self.clickhouse_insert_settings,
            )
            logger.debug(
                f"写入 {len(rows)} 条实时tick数据到 ClickHouse 表 {self.clickhouse_table}"
            )
        except Exception as e:
            logger.error(f"写入ClickHouse失败: {e}", exc_info=True)

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

            logger.debug(f"成功获取 {len(tick_data_list)} 条实时数据")
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
                    logger.debug(
                        f"[批次{batch_id:>3}] 第{round_num:>3}次获取 {len(tick_data_list)} 条实时数据"
                    )

                # 将数据写入 ClickHouse
                self.save_tick_data_to_clickhouse(tick_data_list)

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

                    logger.debug(
                        f"[批次{batch_id:>3}] 第{request_count:>3}次获取 {len(tick_data_list)} 条实时数据"
                    )

                    # 将数据写入 ClickHouse
                    self.save_tick_data_to_clickhouse(tick_data_list)

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
                    params=self._with_token({"date": date_str})
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
        运行时间：9:15-9:25、9:30-11:30、13:00-15:00
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

        window_desc = "、".join([f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in self.trading_windows])
        logger.info(f"实时Tick采集窗口: {window_desc}")

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
                    now_time = datetime.now().time()
                    window_status, reference_time = self._get_trading_window_status(now_time)

                    if window_status != "active":
                        if window_status == "upcoming" and reference_time:
                            logger.info(
                                f"当前时间 {now_time} 不在实时采集窗口，将在 {reference_time.strftime('%H:%M:%S')} 再次开始..."
                            )
                            wait_seconds = (
                                datetime.combine(datetime.now().date(), reference_time)
                                - datetime.combine(datetime.now().date(), now_time)
                            ).total_seconds()
                            await asyncio.sleep(min(max(wait_seconds, 10), 60))
                            continue
                        else:
                            logger.info(f"当前时间 {now_time} 已过今日实时采集时间，任务结束")
                            break  # 结束任务

                    request_count += 1
                    round_start_time = time_module.time()
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                    logger.debug(f"[第{request_count}轮请求] {current_time}")

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
