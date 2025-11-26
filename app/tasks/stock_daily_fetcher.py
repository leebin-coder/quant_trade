"""
股票日线数据获取任务
从 Baostock 获取日线数据并同步到本地数据库
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

import baostock as bs
import httpx
import pandas as pd

from app.core.config import settings
from app.utils.logger import logger


class StockDailyFetcher:
    """股票日线数据获取器"""

    def __init__(self):
        """初始化"""
        self.last_fetch_time: Optional[datetime] = None
        self.api_base_url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api"
        self.batch_size = 1000
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.stock_api_token}"
        }
        # Baostock 登录状态
        self.bs_logged_in = False

        # 频率限制控制（Baostock 没有严格限制，但建议适当控制）
        self.request_count = 0
        self.request_limit = 100  # 每分钟最大请求次数
        self.minute_start_time = None
        self.max_retries = 3
        self.retry_delay = 2  # 重试等待时间（秒）
        self.final_retry_delay = 30  # 最终重试等待时间（秒）

    async def sync_stock_daily(self):
        """
        同步股票日线数据（从 Baostock）
        每天下午4:00执行

        流程：
        1. 获取所有股票基本信息
        2. 遍历每只股票，查询3种复权类型（后复权、前复权、不复权）的最后交易日
        3. 根据最后交易日确定查询起始日期，从 Baostock 获取数据
        4. 汇总3种复权类型的数据，批量插入数据库（1000条/批）
        5. 处理完一只股票后再处理下一只
        """
        logger.info("=" * 80)
        logger.info("开始同步股票日线数据（Baostock）...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # Step 1: 获取所有股票基本信息
            logger.info("\n📊 步骤1: 获取所有股票基本信息...")
            stocks = await self._get_all_stocks()
            if not stocks:
                logger.warning("⚠️  未获取到股票信息，任务结束")
                return

            logger.info(f"✓ 共获取 {len(stocks)} 只股票")

            # 登录 Baostock
            logger.info("\n📊 登录 Baostock...")
            await self._bs_login()

            today = datetime.now().strftime("%Y-%m-%d")
            total_stocks = len(stocks)
            success_count = 0
            fail_count = 0

            # Step 2: 遍历每只股票
            for idx, stock in enumerate(stocks, 1):
                stock_code = stock.get("stockCode")  # 格式: 000001.SH
                list_date = stock.get("listingDate")  # 上市日期
                stock_name = stock.get("stockName", "")

                if not stock_code or not list_date:
                    logger.warning(f"[{idx}/{total_stocks}] 股票信息不完整，跳过")
                    fail_count += 1
                    continue

                logger.info(f"\n[{idx}/{total_stocks}] 处理股票: {stock_code} {stock_name}")
                logger.info(f"  上市日期: {list_date}")

                try:
                    # 转换股票代码格式: 000001.SH -> sh.000001
                    bs_stock_code = self._convert_stock_code(stock_code)

                    # Step 3: 查询3种复权类型的最后交易日
                    logger.info(f"  查询最后交易日...")
                    adjust_flags = [1, 2, 3]  # 1:后复权 2:前复权 3:不复权

                    all_daily_data = []

                    for adjust_flag in adjust_flags:
                        adjust_name = {1: "后复权", 2: "前复权", 3: "不复权"}[adjust_flag]
                        logger.info(f"    处理 {adjust_name} 数据...")

                        # 查询最后一个交易日
                        last_trade_date = await self._get_last_trade_date(stock_code, adjust_flag)

                        # Step 4: 确定查询起始日期
                        if last_trade_date:
                            # 如果有最后交易日，从最后交易日+1天开始
                            start_date_obj = datetime.strptime(last_trade_date, "%Y-%m-%d") + timedelta(days=1)
                            start_date = start_date_obj.strftime("%Y-%m-%d")
                            logger.info(f"      最后交易日: {last_trade_date}，从 {start_date} 开始查询")
                        else:
                            # 如果没有最后交易日，从上市日期开始
                            start_date = list_date
                            logger.info(f"      无历史数据，从上市日期 {start_date} 开始查询")

                        # 如果开始日期大于今天，跳过
                        if start_date > today:
                            logger.info(f"      开始日期 {start_date} 大于今天，跳过")
                            continue

                        # 从 Baostock 获取数据
                        daily_data = await self._fetch_stock_daily_from_baostock(
                            bs_stock_code,
                            start_date,
                            today,
                            adjust_flag
                        )

                        if daily_data:
                            # 转换股票代码格式回 000001.SH
                            for item in daily_data:
                                item["stockCode"] = stock_code
                                item["adjustFlag"] = adjust_flag

                            all_daily_data.extend(daily_data)
                            logger.info(f"      ✓ 获取 {len(daily_data)} 条数据")
                        else:
                            logger.info(f"      无新增数据")

                    # Step 5: 批量插入数据
                    if all_daily_data:
                        logger.info(f"  汇总数据: 共 {len(all_daily_data)} 条")
                        saved = await self._save_daily_data_batch(all_daily_data)
                        if saved:
                            success_count += 1
                            logger.info(f"  ✓ {stock_code} 数据保存成功")
                        else:
                            fail_count += 1
                            logger.error(f"  ✗ {stock_code} 数据保存失败")
                    else:
                        logger.info(f"  无需更新数据")
                        success_count += 1

                except Exception as e:
                    fail_count += 1
                    logger.error(f"  ✗ {stock_code} 处理失败: {str(e)}")
                    continue

            # 登出 Baostock
            await self._bs_logout()

            # 总结
            logger.info("\n" + "=" * 80)
            logger.info(f"✓ 股票日线数据同步完成！")
            logger.info(f"  成功: {success_count}/{total_stocks}")
            logger.info(f"  失败: {fail_count}/{total_stocks}")
            logger.info("=" * 80)

            self.last_fetch_time = datetime.now()

        except Exception as e:
            logger.error(f"\n❌ 股票日线数据同步任务执行失败: {str(e)}", exc_info=True)
            await self._bs_logout()
            raise

    async def _get_latest_daily_date(self) -> Optional[str]:
        """
        查询数据库中最新的日线数据日期

        Returns:
            最新日期字符串（格式: YYYY-MM-DD），如果没有数据则返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/stock-daily/latest-date",
                    headers=self.headers
                )
                response.raise_for_status()

                # 解析 JSON 响应
                result = response.json()

                # 从 data 字段中获取日期数据
                latest_date = result.get("data")

                # 判断是否为有效日期：data 可能是 null、空字符串或有效日期字符串
                if not latest_date or (isinstance(latest_date, str) and latest_date.lower() == "null"):
                    return None

                return latest_date

        except Exception as e:
            logger.error(f"查询最新日线数据日期失败: {str(e)}")
            return None

    async def _get_trade_calendar(self, year: int) -> List[str]:
        """
        获取指定年份的交易日历

        Args:
            year: 年份

        Returns:
            交易日期列表，格式: ['2024-01-02', '2024-01-03', ...]
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/trading-calendar/year/{year}",
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    data = result.get("data", [])
                    # 提取所有交易日（isTradingDay=1）的日期
                    # 字段名：tradeDate, isTradingDay
                    trade_dates = [item["tradeDate"] for item in data if item.get("isTradingDay") == 1]
                    trade_dates.sort()
                    return trade_dates
                else:
                    logger.error(f"获取{year}年交易日历失败: {result.get('message')}")
                    return []

        except Exception as e:
            logger.error(f"获取{year}年交易日历失败: {str(e)}")
            return []

    async def _get_trade_calendar_from_1990(self) -> List[str]:
        """
        获取从1990年到今年的所有交易日历

        Returns:
            交易日期列表，格式: ['1990-12-19', '1990-12-20', ...]
        """
        current_year = datetime.now().year
        all_trade_dates = []

        for year in range(1990, current_year + 1):
            logger.info(f"  获取 {year} 年交易日历...")
            trade_dates = await self._get_trade_calendar(year)
            all_trade_dates.extend(trade_dates)
            await asyncio.sleep(0.1)  # 避免请求过快

        all_trade_dates.sort()
        logger.info(f"✓ 共获取 {len(all_trade_dates)} 个交易日")
        return all_trade_dates

    async def _get_all_stocks(self) -> List[Dict]:
        """
        获取所有股票基本信息

        Returns:
            股票信息列表，包含 stockCode, stockName, listDate 等
        """
        try:
            url = f"{self.api_base_url}/stocks/all"
            logger.info(f"  请求URL: {url}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    url,
                    headers=self.headers
                )

                logger.info(f"  响应状态码: {response.status_code}")

                response.raise_for_status()

                result = response.json()
                logger.info(f"  响应结果: code={result.get('code')}, message={result.get('message')}")

                if result.get("code") == 200:
                    # 从 result.data 中获取数据
                    data = result.get("data", {})

                    # 如果 data 是字典，从 data.data 中获取列表
                    if isinstance(data, dict):
                        stocks = data.get("data", [])
                    else:
                        # 如果 data 直接是列表
                        stocks = data if isinstance(data, list) else []

                    logger.info(f"  获取到 {len(stocks)} 只股票")

                    # 打印前3只股票的信息用于调试
                    if stocks:
                        logger.info("  股票数据示例:")
                        for stock in stocks[:3]:
                            logger.info(f"    {stock}")

                    return stocks
                else:
                    logger.error(f"获取股票列表失败: {result.get('message')}")
                    return []

        except Exception as e:
            logger.error(f"获取股票列表失败: {str(e)}", exc_info=True)
            return []

    async def _get_last_trade_date(self, stock_code: str, adjust_flag: int) -> Optional[str]:
        """
        查询指定股票和复权类型的最后一个交易日

        Args:
            stock_code: 股票代码，格式 000001.SH
            adjust_flag: 复权标识 1:后复权 2:前复权 3:不复权

        Returns:
            最后交易日，格式 YYYY-MM-DD，如果没有则返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/stock-daily/latest-date",
                    params={
                        "stockCode": stock_code,
                        "adjustFlag": adjust_flag
                    },
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    last_date = result.get("data")
                    # 判断是否为有效日期
                    if not last_date or (isinstance(last_date, str) and last_date.lower() in ["null", ""]):
                        return None
                    return last_date
                else:
                    return None

        except Exception as e:
            logger.error(f"查询最后交易日失败: {str(e)}")
            return None

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        转换股票代码格式: 000001.SH -> sh.000001

        Args:
            stock_code: 原始股票代码，格式 000001.SH

        Returns:
            Baostock 格式的股票代码，格式 sh.000001
        """
        if '.' not in stock_code:
            return stock_code

        code, exchange = stock_code.split('.')
        return f"{exchange}.{code}"

    async def _get_all_stock_codes(self) -> List[str]:
        """
        获取所有股票代码

        Returns:
            股票代码列表，格式: ['000001.SZ', '000002.SZ', ...]
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/stock/codes",
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    codes = result.get("data", [])
                    return codes
                else:
                    logger.error(f"获取股票代码列表失败: {result.get('message')}")
                    return []

        except Exception as e:
            logger.error(f"获取股票代码列表失败: {str(e)}")
            return []

    async def _bs_login(self):
        """登录 Baostock"""
        try:
            lg = bs.login()
            if lg.error_code == '0':
                self.bs_logged_in = True
                logger.info("✓ Baostock 登录成功")
            else:
                logger.error(f"✗ Baostock 登录失败: {lg.error_msg}")
                raise Exception(f"Baostock 登录失败: {lg.error_msg}")
        except Exception as e:
            logger.error(f"✗ Baostock 登录异常: {str(e)}")
            raise

    async def _bs_logout(self):
        """登出 Baostock"""
        try:
            if self.bs_logged_in:
                bs.logout()
                self.bs_logged_in = False
                logger.info("✓ Baostock 登出成功")
        except Exception as e:
            logger.error(f"✗ Baostock 登出异常: {str(e)}")

    async def _fetch_stock_daily_from_baostock(
        self, stock_code: str, start_date: str, end_date: str, adjust_flag: int = 3
    ) -> List[Dict]:
        """
        从 Baostock 获取股票日线数据

        Args:
            stock_code: 股票代码，格式如 "sh.601398"
            start_date: 开始日期，格式 YYYY-MM-DD
            end_date: 结束日期，格式 YYYY-MM-DD
            adjust_flag: 复权标识 1:后复权 2:前复权 3:不复权

        Returns:
            日线数据列表
        """
        try:
            # 调用 Baostock API
            # frequency="d" 表示日线
            # adjustflag: "1"=后复权 "2"=前复权 "3"=不复权
            rs = bs.query_history_k_data_plus(
                stock_code,
                "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,psTTM,pcfNcfTTM,pbMRQ,isST",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag=str(adjust_flag)
            )

            if rs.error_code != '0':
                logger.error(f"        Baostock 查询失败: {rs.error_msg}")
                return []

            # 获取数据
            data_list = []
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()

                # 转换数据格式，与后端字段对应
                # 字段顺序: date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,psTTM,pcfNcfTTM,pbMRQ,isST
                daily_item = {
                    "stockCode": row[1],  # code (会在外层被替换为 000001.SH 格式)
                    "tradeDate": row[0],  # date
                    "openPrice": float(row[2]) if row[2] else None,  # open
                    "highPrice": float(row[3]) if row[3] else None,  # high
                    "lowPrice": float(row[4]) if row[4] else None,  # low
                    "closePrice": float(row[5]) if row[5] else None,  # close
                    "preClose": float(row[6]) if row[6] else None,  # preclose
                    "volume": float(row[7]) if row[7] else None,  # volume
                    "amount": float(row[8]) if row[8] else None,  # amount
                    "adjustFlag": adjust_flag,  # adjustFlag (会在外层被设置)
                    "turn": float(row[10]) if row[10] else None,  # turn (换手率)
                    "tradeStatus": int(row[11]) if row[11] else None,  # tradestatus (1正常 0停牌)
                    "pctChange": float(row[12]) if row[12] else None,  # pctChg (涨跌幅)
                    "changeAmount": None,  # changeAmount (涨跌额，Baostock不提供，需要计算)
                    "peTtm": float(row[13]) if row[13] else None,  # peTTM
                    "psTtm": float(row[14]) if row[14] else None,  # psTTM
                    "pcfNcfTtm": float(row[15]) if row[15] else None,  # pcfNcfTTM
                    "pbMrq": float(row[16]) if row[16] else None,  # pbMRQ
                    "isSt": int(row[17]) if row[17] else 0  # isST (1是 0否)
                }

                # 计算涨跌额 changeAmount = closePrice - preClose
                if daily_item["closePrice"] is not None and daily_item["preClose"] is not None:
                    daily_item["changeAmount"] = daily_item["closePrice"] - daily_item["preClose"]

                data_list.append(daily_item)

            return data_list

        except Exception as e:
            logger.error(f"        从 Baostock 获取数据异常: {str(e)}")
            return []

    async def _fetch_daily_by_date(self, trade_date: str) -> List[Dict]:
        """
        获取指定交易日所有股票的日线数据（不传股票代码）

        带重试机制：
        - 失败时等待5秒重试，最多重试3次
        - 3次都失败后等待1分钟再重试一次
        - 如果最终重试还是失败，返回None并结束任务

        Args:
            trade_date: 交易日期，格式: YYYY-MM-DD

        Returns:
            日线数据列表，如果最终失败返回 None（区别于空列表）
        """
        # 转换日期格式 YYYY-MM-DD -> YYYYMMDD
        date_str = trade_date.replace("-", "")

        # 第一阶段：尝试3次，每次失败等待5秒
        for attempt in range(1, self.max_retries + 1):
            try:
                # 检查并控制频率
                await self._check_rate_limit()

                # 调用 Tushare 接口获取该日所有股票的日线数据（不传 ts_code）
                df = self.pro.daily(trade_date=date_str)

                # 请求成功，增加计数
                self.request_count += 1

                if df is None or df.empty:
                    logger.warning(f"  {trade_date} 未获取到数据")
                    return []

                # 转换数据格式
                all_daily_data = []
                for _, row in df.iterrows():
                    daily_item = {
                        "stockCode": row["ts_code"],
                        "tradeDate": f"{row['trade_date'][:4]}-{row['trade_date'][4:6]}-{row['trade_date'][6:8]}",
                        "openPrice": float(row["open"]) if pd.notna(row["open"]) else None,
                        "highPrice": float(row["high"]) if pd.notna(row["high"]) else None,
                        "lowPrice": float(row["low"]) if pd.notna(row["low"]) else None,
                        "closePrice": float(row["close"]) if pd.notna(row["close"]) else None,
                        "preClose": float(row["pre_close"]) if pd.notna(row["pre_close"]) else None,
                        "changeAmount": float(row["change"]) if pd.notna(row["change"]) else None,
                        "pctChange": float(row["pct_chg"]) if pd.notna(row["pct_chg"]) else None,
                        "volume": float(row["vol"]) if pd.notna(row["vol"]) else None,
                        "amount": float(row["amount"]) if pd.notna(row["amount"]) else None
                    }
                    all_daily_data.append(daily_item)

                logger.info(f"  从Tushare获取到 {len(all_daily_data)} 条记录")
                return all_daily_data

            except Exception as e:
                logger.error(f"  从Tushare获取 {trade_date} 数据失败 (尝试 {attempt}/{self.max_retries}): {str(e)}")

                if attempt < self.max_retries:
                    logger.info(f"  等待 {self.retry_delay} 秒后重试...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    # 3次都失败了，进入最终重试阶段
                    logger.warning(f"  {trade_date} 已重试 {self.max_retries} 次失败，等待 {self.final_retry_delay} 秒后进行最终重试...")
                    await asyncio.sleep(self.final_retry_delay)

        # 第二阶段：最终重试一次
        try:
            logger.info(f"  {trade_date} 开始最终重试...")

            # 检查并控制频率
            await self._check_rate_limit()

            # 调用 Tushare 接口
            df = self.pro.daily(trade_date=date_str)

            # 请求成功，增加计数
            self.request_count += 1

            if df is None or df.empty:
                logger.error(f"  {trade_date} 最终重试仍未获取到数据，任务将结束")
                return None

            # 转换数据格式
            all_daily_data = []
            for _, row in df.iterrows():
                daily_item = {
                    "stockCode": row["ts_code"],
                    "tradeDate": f"{row['trade_date'][:4]}-{row['trade_date'][4:6]}-{row['trade_date'][6:8]}",
                    "openPrice": float(row["open"]) if pd.notna(row["open"]) else None,
                    "highPrice": float(row["high"]) if pd.notna(row["high"]) else None,
                    "lowPrice": float(row["low"]) if pd.notna(row["low"]) else None,
                    "closePrice": float(row["close"]) if pd.notna(row["close"]) else None,
                    "preClose": float(row["pre_close"]) if pd.notna(row["pre_close"]) else None,
                    "changeAmount": float(row["change"]) if pd.notna(row["change"]) else None,
                    "pctChange": float(row["pct_chg"]) if pd.notna(row["pct_chg"]) else None,
                    "volume": float(row["vol"]) if pd.notna(row["vol"]) else None,
                    "amount": float(row["amount"]) if pd.notna(row["amount"]) else None
                }
                all_daily_data.append(daily_item)

            logger.info(f"  最终重试成功，从Tushare获取到 {len(all_daily_data)} 条记录")
            return all_daily_data

        except Exception as e:
            logger.error(f"  {trade_date} 最终重试失败: {str(e)}，任务将结束")
            return None

    async def _check_rate_limit(self):
        """
        检查并控制API调用频率
        从第一次请求Tushare开始计时，每分钟最多45次请求
        """
        current_time = time.time()

        # 如果是第一次请求，记录开始时间
        if self.minute_start_time is None:
            self.minute_start_time = current_time
            logger.info(f"⏱️  开始计时，每分钟最多 {self.request_limit} 次请求")
            return

        # 计算从第一次请求到现在经过的时间
        elapsed = current_time - self.minute_start_time

        # 如果已经超过1分钟，重置计数和开始时间
        if elapsed >= 60:
            self.request_count = 0
            self.minute_start_time = current_time
            logger.info(f"⏱️  新的一分钟开始，重置计数器")
            return

        # 如果达到限制，等待到下一分钟
        if self.request_count >= self.request_limit:
            wait_time = 60 - elapsed
            if wait_time > 0:
                logger.info(f"⏸️  已达到频率限制({self.request_limit}次/分钟)，等待 {wait_time:.1f} 秒到下一分钟...")
                await asyncio.sleep(wait_time)
            # 重置计数和时间
            self.request_count = 0
            self.minute_start_time = time.time()
            logger.info(f"⏱️  新的一分钟开始，重置计数器")

    async def _save_daily_data_batch(self, daily_data: List[Dict]) -> bool:
        """
        批量保存日线数据到数据库（分批插入，每批1000条）

        Args:
            daily_data: 日线数据列表

        Returns:
            是否全部保存成功
        """
        if not daily_data:
            return False

        try:
            total = len(daily_data)
            batch_size = self.batch_size  # 1000
            batches = (total + batch_size - 1) // batch_size  # 向上取整

            logger.info(f"  开始批量保存，共 {total} 条数据，分 {batches} 批")

            success_count = 0
            fail_count = 0

            for i in range(0, total, batch_size):
                batch = daily_data[i:i + batch_size]
                batch_num = i // batch_size + 1

                logger.info(f"    批次 {batch_num}/{batches}: 正在保存 {len(batch)} 条...")

                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        response = await client.post(
                            f"{self.api_base_url}/stock-daily/batch",
                            json=batch,
                            headers=self.headers
                        )
                        response.raise_for_status()

                        result = response.json()
                        if result.get("code") == 200:
                            success_count += len(batch)
                            logger.info(f"    批次 {batch_num}/{batches}: ✓ 保存成功")
                        else:
                            fail_count += len(batch)
                            logger.error(f"    批次 {batch_num}/{batches}: ✗ 保存失败 - {result.get('message')}")

                except Exception as e:
                    fail_count += len(batch)
                    logger.error(f"    批次 {batch_num}/{batches}: ✗ 保存异常 - {str(e)}")

            logger.info(f"  批量保存完成: 成功 {success_count}/{total}, 失败 {fail_count}/{total}")
            return fail_count == 0

        except Exception as e:
            logger.error(f"  批量保存失败: {str(e)}")
            return False

    async def _save_daily_data(self, daily_data: List[Dict]) -> bool:
        """
        批量保存日线数据到数据库

        Args:
            daily_data: 日线数据列表

        Returns:
            是否保存成功
        """
        if not daily_data:
            return False

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f"{self.api_base_url}/stock-daily/batch",
                    json=daily_data,
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    return True
                else:
                    logger.error(f"保存日线数据失败: {result.get('message')}")
                    return False

        except Exception as e:
            logger.error(f"保存日线数据失败: {str(e)}")
            return False
