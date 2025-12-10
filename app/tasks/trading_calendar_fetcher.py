"""
交易日历数据获取任务
从 Baostock 获取交易日历并同步到本地数据库
"""
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import baostock as bs
import httpx
import pandas as pd

from app.core.config import settings
from app.utils.logger import logger


class TradingCalendarFetcher:
    """交易日历数据获取器"""

    def __init__(self):
        """初始化"""
        self.last_fetch_time: Optional[datetime] = None
        self.api_base_url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api"
        self.batch_size = 1000
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.stock_api_token}"
        }
        self._auth_params = {"token": settings.stock_api_token}

    def _with_token(self, extra_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = dict(self._auth_params)
        if extra_params:
            params.update(extra_params)
        return params

    async def sync_trading_calendar(self):
        """
        同步交易日历数据
        每天凌晨执行一次

        流程：
        1. 查询数据库中最新的交易日
        2. 如果最新交易日在当前时间之后，则不做任何操作
        3. 如果最新交易日在当前时间之前，则从最新交易日开始查询一年数据
        4. 如果数据库为空，则从1990-12-01开始，每次查询2年数据
        """
        logger.info("=" * 80)
        logger.info("开始同步交易日历数据...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中最新的交易日
            logger.info("📊 步骤1: 查询数据库中最新的交易日...")
            latest_trade_date = await self._get_latest_trade_date()

            current_date = datetime.now().date()

            if latest_trade_date:
                logger.info(f"✓ 数据库中最新交易日: {latest_trade_date}")
                logger.info(f"  当前日期: {current_date}")

                # 1.1 如果最新交易日在当前时间之后，则不做任何操作
                if latest_trade_date >= current_date:
                    logger.info("✓ 交易日历数据已是最新，无需更新")
                    return

                # 1.2 如果最新交易日在当前时间之前，从最新交易日的下一天开始查询整整一年
                logger.info(f"\n📊 步骤2: 从 {latest_trade_date} 之后开始查询整整一年数据...")
                start_date = latest_trade_date + timedelta(days=1)
                end_date = start_date + timedelta(days=365)

                logger.info(f"查询范围: {start_date} 至 {end_date}")
                await self._fetch_and_save_calendar(
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d")
                )

            else:
                # 2. 数据库为空，从1990-12-01开始，每次查询整整2年
                logger.info("✓ 数据库中没有交易日历数据")
                logger.info(f"\n📊 步骤2: 从 1990-12-01 开始，每次查询整整2年数据...")

                start_date = datetime.strptime("1990-12-01", "%Y-%m-%d").date()

                while start_date < current_date:
                    # 计算结束日期（整整2年后）
                    end_date = start_date + timedelta(days=730)  # 2年 = 730天

                    logger.info(f"\n正在查询: {start_date} 至 {end_date}")
                    await self._fetch_and_save_calendar(
                        start_date.strftime("%Y-%m-%d"),
                        end_date.strftime("%Y-%m-%d")
                    )

                    # 下一个周期从结束日期的下一天开始
                    start_date = end_date + timedelta(days=1)

                    # 避免请求过快
                    await asyncio.sleep(1)

            self.last_fetch_time = datetime.now()
            logger.info("\n" + "=" * 80)
            logger.info("✓ 交易日历数据同步完成！")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"交易日历同步失败: {e}", exc_info=True)
            raise

    async def _get_latest_trade_date(self) -> Optional[datetime.date]:
        """
        查询数据库中最新的交易日

        Returns:
            Optional[datetime.date]: 最新交易日，如果数据库为空则返回 None
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.api_base_url}/trading-calendar/latest",
                    headers=self.headers,
                    params=self._with_token()
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    data = result.get("data")
                    if data and data.get("tradeDate"):
                        # 解析日期字符串 "yyyy-MM-dd"
                        trade_date_str = data.get("tradeDate")
                        return datetime.strptime(trade_date_str, "%Y-%m-%d").date()
                    else:
                        return None
                else:
                    logger.error(f"查询最新交易日失败: {result.get('message')}")
                    return None

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # 404 表示没有数据
                return None
            logger.error(f"查询最新交易日接口请求失败: {e}")
            return None
        except httpx.HTTPError as e:
            logger.error(f"查询最新交易日接口请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"查询最新交易日时发生错误: {e}", exc_info=True)
            return None

    async def _fetch_and_save_calendar(self, start_date: str, end_date: str):
        """
        从 Baostock 获取交易日历并保存到数据库

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        """
        # 从 Baostock 获取数据
        calendar_data = await self._fetch_from_baostock(start_date, end_date)

        if not calendar_data:
            logger.warning(f"未获取到交易日历数据: {start_date} 至 {end_date}")
            return

        # 批量保存到数据库
        await self._batch_save_calendar(calendar_data)

    async def _fetch_from_baostock(self, start_date: str, end_date: str) -> List[Dict]:
        """
        从 Baostock 获取交易日历数据

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            List[Dict]: 交易日历数据列表
        """
        try:
            logger.info(f"从 Baostock 获取交易日历: {start_date} 至 {end_date}")

            # 在异步环境中运行同步的 baostock 调用
            loop = asyncio.get_event_loop()

            # 登录
            lg = await loop.run_in_executor(None, bs.login)
            if lg.error_code != '0':
                logger.error(f"Baostock 登录失败: {lg.error_msg}")
                return []

            try:
                # 查询交易日历
                rs = await loop.run_in_executor(
                    None,
                    lambda: bs.query_trade_dates(start_date=start_date, end_date=end_date)
                )

                if rs.error_code != '0':
                    logger.error(f"查询交易日历失败: {rs.error_msg}")
                    return []

                # 获取数据
                data_list = []
                while await loop.run_in_executor(None, rs.next):
                    row_data = await loop.run_in_executor(None, rs.get_row_data)
                    data_list.append(row_data)

                # 转换为 DataFrame
                df = pd.DataFrame(data_list, columns=rs.fields)

                if df.empty:
                    logger.warning(f"未获取到数据: {start_date} 至 {end_date}")
                    return []

                logger.info(f"✓ 从 Baostock 获取到 {len(df)} 条交易日历记录")

                # 转换为字典列表
                calendar_data = []
                for _, row in df.iterrows():
                    calendar_data.append({
                        "tradeDate": row["calendar_date"],
                        "isTradingDay": int(row["is_trading_day"])
                    })

                return calendar_data

            finally:
                # 登出
                await loop.run_in_executor(None, bs.logout)

        except Exception as e:
            logger.error(f"从 Baostock 获取交易日历失败: {e}", exc_info=True)
            return []

    async def _batch_save_calendar(self, calendar_data: List[Dict]):
        """
        批量保存交易日历数据到数据库

        Args:
            calendar_data: 交易日历数据列表
        """
        if not calendar_data:
            return

        total = len(calendar_data)
        logger.info(f"准备批量保存 {total} 条交易日历数据...")

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                # 分批保存，每批1000条
                batches = (total + self.batch_size - 1) // self.batch_size
                success_count = 0

                for i in range(batches):
                    start_idx = i * self.batch_size
                    end_idx = min((i + 1) * self.batch_size, total)
                    batch = calendar_data[start_idx:end_idx]

                    logger.info(f"正在保存第 {i+1}/{batches} 批，共 {len(batch)} 条记录...")

                    response = await client.post(
                        f"{self.api_base_url}/trading-calendar/batch",
                        json=batch,
                        headers=self.headers,
                        params=self._with_token()
                    )
                    response.raise_for_status()

                    result = response.json()
                    if result.get("code") == 200:
                        success_count += len(batch)
                        logger.info(f"✓ 第 {i+1} 批保存成功，已累计成功 {success_count}/{total} 条")
                    else:
                        logger.error(f"✗ 第 {i+1} 批保存失败: {result.get('message')}")

                    # 避免请求过快
                    if i < batches - 1:
                        await asyncio.sleep(0.5)

                logger.info(f"\n批量保存完成: 成功 {success_count}/{total} 条")

        except httpx.HTTPError as e:
            logger.error(f"批量保存交易日历失败: {e}")
            raise
        except Exception as e:
            logger.error(f"批量保存交易日历时发生错误: {e}", exc_info=True)
            raise
