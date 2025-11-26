"""
股票日线数据获取任务
从 Tushare 获取日线数据并同步到本地数据库
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import time

import tushare as ts
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
        # 初始化 tushare pro
        self.tushare_token = "347ae3b92b9a97638f155512bc599767558b94c3dcb47f5abd058b95"
        ts.set_token(self.tushare_token)
        self.pro = ts.pro_api()

        # 频率限制控制
        self.request_count = 0  # 当前分钟内的请求计数
        self.request_limit = 45  # 每分钟最大请求次数
        self.minute_start_time = None  # 第一次请求的时间，用于计算一分钟周期
        self.max_retries = 3  # 单次请求最大重试次数
        self.retry_delay = 5  # 每次重试等待时间（秒）
        self.final_retry_delay = 60  # 三次失败后的最终重试等待时间（秒）

    async def sync_stock_daily(self):
        """
        同步股票日线数据
        每天下午5:20执行一次

        流程：
        1. 查询数据库中最新的日线数据日期
        2. 如果没有则从1990年开始查交易日，获取到距今天最近的一个交易日（包括今天）的所有交易日
        3. 如果有最新日期：
           - 今天是交易日且返回的日期是今天 → 直接结束
           - 今天是交易日且返回的日期是前一个交易日 → 只查今天
           - 今天不是交易日 → 从返回的日期开始查到今天前的一个交易日
        4. 拿到所有要查的交易日后，开始一天一天的查 Tushare（不传股票代码）
        5. 从 Tushare 查到数据后直接调用后端接口保存
        """
        logger.info("=" * 80)
        logger.info("开始同步股票日线数据...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中最新的日线数据日期
            logger.info("📊 步骤1: 查询数据库中最新的日线数据日期...")
            latest_date = await self._get_latest_daily_date()

            # 2. 获取交易日历（到今天为止）
            today = datetime.now().strftime("%Y-%m-%d")
            logger.info("\n📊 步骤2: 获取交易日历...")

            if latest_date:
                logger.info(f"✓ 数据库中最新日线数据日期: {latest_date}")
                # 获取从最新日期所在年到今年的交易日历
                start_year = datetime.strptime(latest_date, "%Y-%m-%d").year
                current_year = datetime.now().year
                trade_dates = []
                for year in range(start_year, current_year + 1):
                    logger.info(f"  获取 {year} 年交易日历...")
                    year_dates = await self._get_trade_calendar(year)
                    trade_dates.extend(year_dates)
                    await asyncio.sleep(0.1)
                trade_dates.sort()
            else:
                logger.info("✓ 数据库中没有日线数据，从1990年开始查询交易日历")
                # 从1990年开始查询所有交易日历到今天
                trade_dates = await self._get_trade_calendar_from_1990()

            if not trade_dates:
                logger.warning("⚠️  未获取到交易日历数据，任务结束")
                return

            # 只保留到今天为止的交易日（包括今天）
            trade_dates = [d for d in trade_dates if d <= today]
            logger.info(f"✓ 共获取 {len(trade_dates)} 个交易日（截止到今天）")

            # 3. 确定需要同步的交易日期范围
            logger.info("\n📊 步骤3: 确定需要同步的日期范围...")

            if latest_date:
                # 检查今天是否是交易日
                is_today_trading = today in trade_dates

                if is_today_trading:
                    if latest_date == today:
                        # 今天是交易日且返回的日期是今天 → 直接结束
                        logger.info("✓ 最新数据已是今天，无需同步")
                        return
                    else:
                        # 今天是交易日且返回的日期不是今天
                        # 找到最新日期的下一个交易日
                        if latest_date in trade_dates:
                            latest_idx = trade_dates.index(latest_date)
                            # 获取从下一个交易日到今天的所有交易日
                            dates_to_sync = trade_dates[latest_idx + 1:]
                            dates_to_sync = [d for d in dates_to_sync if d <= today]
                        else:
                            # 如果最新日期不在交易日列表中，从最新日期之后的第一个交易日开始
                            dates_to_sync = [d for d in trade_dates if d > latest_date and d <= today]

                        if not dates_to_sync:
                            logger.info("✓ 已是最新数据，无需同步")
                            return
                else:
                    # 今天不是交易日 → 从返回的日期的下一个交易日查到今天前的一个交易日
                    if latest_date in trade_dates:
                        latest_idx = trade_dates.index(latest_date)
                        # 获取从下一个交易日开始的所有交易日（今天不是交易日，所以不会包含今天）
                        dates_to_sync = trade_dates[latest_idx + 1:]
                        dates_to_sync = [d for d in dates_to_sync if d < today]
                    else:
                        # 如果最新日期不在交易日列表中，从最新日期之后的第一个交易日开始
                        dates_to_sync = [d for d in trade_dates if d > latest_date and d < today]

                    if not dates_to_sync:
                        logger.info("✓ 今天不是交易日，且已是最新数据，无需同步")
                        return

                logger.info(f"✓ 需要同步 {len(dates_to_sync)} 个交易日的数据")
                logger.info(f"  起始日期: {dates_to_sync[0]}")
                logger.info(f"  结束日期: {dates_to_sync[-1]}")
            else:
                # 从1990年第一个交易日开始到今天（或今天前的一个交易日）
                dates_to_sync = trade_dates
                logger.info(f"✓ 需要同步 {len(dates_to_sync)} 个交易日的数据（从1990年开始）")
                logger.info(f"  起始日期: {dates_to_sync[0]}")
                logger.info(f"  结束日期: {dates_to_sync[-1]}")

            # 4. 逐个交易日同步数据（不传股票代码，直接从Tushare按日期查询）
            logger.info("\n📊 步骤4: 开始逐个交易日从Tushare同步数据...")
            total_dates = len(dates_to_sync)
            success_count = 0
            fail_count = 0

            for idx, trade_date in enumerate(dates_to_sync, 1):
                logger.info(f"\n[{idx}/{total_dates}] 正在同步 {trade_date} 的日线数据...")

                try:
                    # 从Tushare获取该交易日的所有股票日线数据（不传股票代码）
                    daily_data = await self._fetch_daily_by_date(trade_date)

                    # 检查是否是最终失败（返回None）
                    if daily_data is None:
                        logger.error(f"❌ {trade_date} 数据获取最终失败，任务结束")
                        logger.info("\n" + "=" * 80)
                        logger.info(f"✗ 股票日线数据同步被中断！")
                        logger.info(f"  成功: {success_count}/{idx}")
                        logger.info(f"  失败: {fail_count + 1}/{idx}")
                        logger.info(f"  中断于: {trade_date}")
                        logger.info("=" * 80)
                        return

                    if daily_data:
                        # 直接保存到数据库
                        saved = await self._save_daily_data(daily_data)
                        if saved:
                            success_count += 1
                            logger.info(f"✓ {trade_date} 数据保存成功，共 {len(daily_data)} 条记录")
                        else:
                            fail_count += 1
                            logger.error(f"✗ {trade_date} 数据保存失败")
                    else:
                        # 空列表，表示该日期没有数据（非交易日或其他原因）
                        logger.warning(f"⚠️  {trade_date} 未获取到数据")

                except Exception as e:
                    fail_count += 1
                    logger.error(f"✗ {trade_date} 数据同步失败: {str(e)}")
                    continue

            # 5. 总结
            logger.info("\n" + "=" * 80)
            logger.info(f"✓ 股票日线数据同步完成！")
            logger.info(f"  成功: {success_count}/{total_dates}")
            logger.info(f"  失败: {fail_count}/{total_dates}")
            logger.info("=" * 80)

            self.last_fetch_time = datetime.now()

        except Exception as e:
            logger.error(f"\n❌ 股票日线数据同步任务执行失败: {str(e)}", exc_info=True)
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
