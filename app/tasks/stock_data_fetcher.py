"""
股票基本信息获取任务
获取A股的基本信息并同步到本地数据库
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import tushare as ts
import httpx

from app.core.config import settings
from app.utils.logger import logger

class StockDataFetcher:
    """股票数据获取器"""

    def __init__(self):
        """初始化"""
        self.last_fetch_time: Optional[datetime] = None
        self.api_base_url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api"
        self.batch_size = settings.stock_batch_size
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.stock_api_token}"
        }
        # 初始化 tushare pro
        self.tushare_token = "347ae3b92b9a97638f155512bc599767558b94c3dcb47f5abd058b95"
        ts.set_token(self.tushare_token)
        self.pro = ts.pro_api()

    async def fetch_all_stock_info(self):
        """
        获取A股股票基本信息并同步到数据库
        每天凌晨00:00执行一次

        流程：
        1. 查询数据库中已存在的股票
        2. 从数据源获取所有A股股票信息
        3. 比对差异，找出需要插入的股票
        4. 分批插入新股票
        """
        logger.info("=" * 80)
        logger.info("开始同步股票基本信息...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中已存在的股票
            logger.info("📊 步骤1: 查询数据库中已存在的A股股票...")
            existing_stocks = await self._query_existing_stocks()
            existing_codes = {stock["stockCode"] for stock in existing_stocks}
            logger.info(f"✓ 数据库中已存在 {len(existing_codes)} 支A股股票")

            # 2. 获取所有A股股票信息
            logger.info("\n📊 步骤2: 从数据源获取所有A股股票信息...")
            all_stocks = await self._fetch_a_share_info()
            logger.info(f"✓ 从数据源获取到 {len(all_stocks)} 支A股股票")

            # 3. 比对差异，找出需要插入的股票
            logger.info("\n📊 步骤3: 比对差异，筛选需要插入的股票...")
            stocks_to_insert = [
                stock for stock in all_stocks if stock["stockCode"] not in existing_codes
            ]
            logger.info(f"✓ 发现 {len(stocks_to_insert)} 支新股票需要插入")

            # 4. 分批插入
            if stocks_to_insert:
                logger.info(f"\n📊 步骤4: 分批插入新股票（每批{self.batch_size}条）...")
                await self._batch_insert_stocks(stocks_to_insert)
            else:
                logger.info("\n✓ 没有新股票需要插入，数据已是最新")

            self.last_fetch_time = datetime.now()
            logger.info("\n" + "=" * 80)
            logger.info("✓ A股股票基本信息同步完成！")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"股票信息同步失败: {e}", exc_info=True)
            raise

    async def _query_existing_stocks(self) -> List[Dict]:
        """
        查询数据库中已存在的A股股票

        Returns:
            List[Dict]: 已存在的股票列表
        """
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                response = await client.post(
                    f"{self.api_base_url}/stocks/query",
                    json={
                        "exchanges": ["SSE", "SZSE", "BSE"]
                    },
                    headers=self.headers
                )
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    return result.get("data", [])
                else:
                    logger.error(f"查询股票失败: {result.get('message')}")
                    return []

        except httpx.HTTPError as e:
            logger.error(f"查询股票接口请求失败: {e}")
            return []
        except Exception as e:
            logger.error(f"查询股票时发生错误: {e}", exc_info=True)
            return []

    async def _fetch_a_share_info(self) -> List[Dict]:
        """
        从 Tushare Pro 获取所有A股股票基本信息

        Returns:
            List[Dict]: 股票信息列表
        """
        try:
            # 在异步环境中运行同步的 tushare 调用
            loop = asyncio.get_event_loop()

            # 使用 tushare pro 的 stock_basic 接口获取所有上市股票
            # list_status='L' 表示上市状态
            df = await loop.run_in_executor(
                None,
                lambda: self.pro.stock_basic(
                    list_status='L',
                    fields='ts_code,symbol,name,area,industry,list_date,fullname,enname,cnspell,market,exchange,curr_type,list_status,delist_date,is_hs,act_name,act_ent_type'
                )
            )

            if df is None or df.empty:
                logger.warning("未获取到A股数据")
                return []

            stocks = []
            for _, row in df.iterrows():
                try:
                    # tushare 返回的字段映射
                    ts_code = str(row.get("ts_code", ""))   # 格式：000001.SZ
                    exchange = str(row.get("exchange", ""))  # SSE/SZSE/BSE

                    if not ts_code or not exchange:
                        continue

                    # 处理日期格式：tushare 返回 YYYYMMDD 格式，需要转换为 YYYY-MM-DD
                    list_date = str(row.get("list_date", ""))
                    if list_date and len(list_date) == 8:
                        list_date = f"{list_date[:4]}-{list_date[4:6]}-{list_date[6:]}"
                    else:
                        list_date = None

                    delist_date = str(row.get("delist_date", ""))
                    if delist_date and len(delist_date) == 8:
                        delist_date = f"{delist_date[:4]}-{delist_date[4:6]}-{delist_date[6:]}"
                    else:
                        delist_date = None

                    # 构建股票信息字典
                    stock_info = {
                        "exchange": exchange,
                        "stockCode": ts_code,
                        "stockName": str(row.get("name", "")),
                        "area": str(row.get("area", "")) if row.get("area") else None,
                        "industry": str(row.get("industry", "")) if row.get("industry") else None,
                        "listingDate": list_date,
                        "fullName": str(row.get("fullname", "")) if row.get("fullname") else None,
                        "enName": str(row.get("enname", "")) if row.get("enname") else None,
                        "cnSpell": str(row.get("cnspell", "")) if row.get("cnspell") else None,
                        "market": str(row.get("market", "")) if row.get("market") else None,
                        "currType": str(row.get("curr_type", "")) if row.get("curr_type") else None,
                        "status": str(row.get("list_status", "")),
                        "delistDate": delist_date,
                        "isHs": str(row.get("is_hs", "")) if row.get("is_hs") else None,
                        "actName": str(row.get("act_name", "")) if row.get("act_name") else None,
                        "actEntType": str(row.get("act_ent_type", "")) if row.get("act_ent_type") else None,
                    }

                    stocks.append(stock_info)

                except Exception as e:
                    logger.warning(f"解析股票数据失败: {row}, 错误: {e}")
                    continue

            logger.info(f"成功从 Tushare Pro 获取 {len(stocks)} 支A股股票信息")
            return stocks

        except Exception as e:
            logger.error(f"获取A股数据失败: {e}", exc_info=True)
            return []

    async def _batch_insert_stocks(self, stocks: List[Dict]):
        """
        分批次插入股票数据

        Args:
            stocks: 待插入的股票列表
        """
        total = len(stocks)
        batches = (total + self.batch_size - 1) // self.batch_size  # 向上取整

        success_count = 0
        fail_count = 0

        async with httpx.AsyncClient(timeout=None) as client:
            for i in range(batches):
                start_idx = i * self.batch_size
                end_idx = min((i + 1) * self.batch_size, total)
                batch = stocks[start_idx:end_idx]

                logger.info(f"正在插入第 {i+1}/{batches} 批，共 {len(batch)} 条记录...")

                try:
                    response = await client.post(
                        f"{self.api_base_url}/stocks/batch",
                        json=batch,
                        headers=self.headers
                    )
                    response.raise_for_status()

                    result = response.json()
                    if result.get("code") == 200:
                        success_count += len(batch)
                        logger.info(f"✓ 第 {i+1} 批插入成功，已累计成功 {success_count}/{total} 条")
                    else:
                        fail_count += len(batch)
                        logger.error(f"✗ 第 {i+1} 批插入失败: {result.get('message')}")

                except httpx.HTTPError as e:
                    fail_count += len(batch)
                    logger.error(f"✗ 第 {i+1} 批插入请求失败: {e}")
                except Exception as e:
                    fail_count += len(batch)
                    logger.error(f"✗ 第 {i+1} 批插入时发生错误: {e}")

                # 避免请求过快，稍作延迟
                if i < batches - 1:
                    await asyncio.sleep(0.5)

        logger.info(f"\n批量插入完成: 成功 {success_count} 条, 失败 {fail_count} 条")
