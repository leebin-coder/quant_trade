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
        self.request_limit = 450  # 每分钟最大请求次数
        self.last_reset_time = time.time()  # 上次重置计数的时间

    async def sync_stock_daily(self):
        """
        同步股票日线数据
        每天下午4点执行一次

        流程：
        1. 查询数据库中最新的日线数据日期
        2. 如果返回null，则从1990年开始查询交易日历
        3. 如果返回日期，则查询当年的交易日历
        4. 判断今天是否为交易日，如果不是则直接结束
        5. 如果是交易日且在今天之前，从返回的日期后一个交易日开始
        6. 逐个交易日请求日线数据，直到今天为止
        7. 每个交易日请求到数据后调用后端接口保存
        8. 每调用450次Tushare接口，停止10秒
        """
        logger.info("=" * 80)
        logger.info("开始同步股票日线数据...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中最新的日线数据日期
            logger.info("📊 步骤1: 查询数据库中最新的日线数据日期...")
            latest_date = await self._get_latest_daily_date()

            # 2. 获取交易日历
            logger.info("\n📊 步骤2: 获取交易日历...")
            if latest_date:
                logger.info(f"✓ 数据库中最新日线数据日期: {latest_date}")
                # 查询当年的交易日历
                year = datetime.strptime(latest_date, "%Y-%m-%d").year
                trade_dates = await self._get_trade_calendar(year)
            else:
                logger.info("✓ 数据库中没有日线数据，从1990年开始查询交易日历")
                # 从1990年开始查询所有交易日历
                trade_dates = await self._get_trade_calendar_from_1990()

            if not trade_dates:
                logger.warning("⚠️  未获取到交易日历数据，任务结束")
                return

            # 3. 判断今天是否为交易日
            today = datetime.now().strftime("%Y-%m-%d")
            logger.info(f"\n📊 步骤3: 判断今天 {today} 是否为交易日...")

            if today not in trade_dates:
                logger.info("✓ 今天不是交易日，任务结束")
                return

            logger.info("✓ 今天是交易日，继续执行")

            # 4. 确定需要同步的交易日期范围
            logger.info("\n📊 步骤4: 确定需要同步的日期范围...")
            if latest_date:
                # 找到最新日期之后的交易日
                start_idx = trade_dates.index(latest_date) + 1 if latest_date in trade_dates else 0
                dates_to_sync = trade_dates[start_idx:]

                # 只同步到今天（包括今天）
                dates_to_sync = [d for d in dates_to_sync if d <= today]

                if not dates_to_sync:
                    logger.info("✓ 已是最新数据，无需同步")
                    return

                logger.info(f"✓ 需要同步 {len(dates_to_sync)} 个交易日的数据")
                logger.info(f"  起始日期: {dates_to_sync[0]}")
                logger.info(f"  结束日期: {dates_to_sync[-1]}")
            else:
                # 从1990年开始到今天的所有交易日
                dates_to_sync = [d for d in trade_dates if d <= today]
                logger.info(f"✓ 需要同步 {len(dates_to_sync)} 个交易日的数据（从1990年开始）")
                logger.info(f"  起始日期: {dates_to_sync[0]}")
                logger.info(f"  结束日期: {dates_to_sync[-1]}")

            # 5. 获取所有股票代码
            logger.info("\n📊 步骤5: 获取所有股票代码...")
            stock_codes = await self._get_all_stock_codes()
            logger.info(f"✓ 获取到 {len(stock_codes)} 只股票")

            # 6. 逐个交易日同步数据
            logger.info("\n📊 步骤6: 开始逐个交易日同步数据...")
            total_dates = len(dates_to_sync)
            success_count = 0
            fail_count = 0

            for idx, trade_date in enumerate(dates_to_sync, 1):
                logger.info(f"\n[{idx}/{total_dates}] 正在同步 {trade_date} 的日线数据...")

                try:
                    # 获取该交易日所有股票的日线数据
                    daily_data = await self._fetch_daily_by_date(trade_date, stock_codes)

                    if daily_data:
                        # 保存到数据库
                        saved = await self._save_daily_data(daily_data)
                        if saved:
                            success_count += 1
                            logger.info(f"✓ {trade_date} 数据保存成功，共 {len(daily_data)} 条记录")
                        else:
                            fail_count += 1
                            logger.error(f"✗ {trade_date} 数据保存失败")
                    else:
                        logger.warning(f"⚠️  {trade_date} 未获取到数据")

                except Exception as e:
                    fail_count += 1
                    logger.error(f"✗ {trade_date} 数据同步失败: {str(e)}")
                    continue

            # 7. 总结
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
                    # 提取所有交易日（is_open=1）的日期
                    trade_dates = [item["calendar_date"] for item in data if item.get("is_open") == 1]
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

    async def _fetch_daily_by_date(self, trade_date: str, stock_codes: List[str]) -> List[Dict]:
        """
        获取指定交易日所有股票的日线数据

        Args:
            trade_date: 交易日期，格式: YYYY-MM-DD
            stock_codes: 股票代码列表

        Returns:
            日线数据列表
        """
        all_daily_data = []

        # 转换日期格式 YYYY-MM-DD -> YYYYMMDD
        date_str = trade_date.replace("-", "")

        # 逐个股票获取数据（按照Tushare的要求）
        total_stocks = len(stock_codes)
        for idx, ts_code in enumerate(stock_codes, 1):
            try:
                # 检查并控制频率
                await self._check_rate_limit()

                # 调用 Tushare 接口获取日线数据
                df = self.pro.daily(
                    ts_code=ts_code,
                    trade_date=date_str
                )

                self.request_count += 1

                if df is not None and not df.empty:
                    # 转换数据格式
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

                # 每处理100只股票输出一次进度
                if idx % 100 == 0:
                    logger.info(f"  进度: {idx}/{total_stocks}, 已获取 {len(all_daily_data)} 条记录")

            except Exception as e:
                logger.warning(f"  获取 {ts_code} 的数据失败: {str(e)}")
                continue

        return all_daily_data

    async def _check_rate_limit(self):
        """
        检查并控制API调用频率
        每分钟不超过450次，每调用450次停止10秒
        """
        current_time = time.time()

        # 如果超过1分钟，重置计数
        if current_time - self.last_reset_time >= 60:
            self.request_count = 0
            self.last_reset_time = current_time

        # 如果达到限制，暂停10秒
        if self.request_count >= self.request_limit:
            logger.info(f"⏸️  已达到频率限制({self.request_limit}次/分钟)，暂停10秒...")
            await asyncio.sleep(10)
            self.request_count = 0
            self.last_reset_time = time.time()

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
