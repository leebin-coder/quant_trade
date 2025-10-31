"""
股票基本信息获取任务
获取A股的基本信息并同步到本地数据库
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Set

import akshare as ak
import httpx

from app.core.config import settings
from app.utils.logger import logger

## TODO 后续基础数据量足够的时候 每天 或者每天跑一次即可
class StockDataFetcher:
    """股票数据获取器"""

    def __init__(self):
        """初始化"""
        self.last_fetch_time: Optional[datetime] = None
        self.api_base_url = f"http://{settings.stock_api_host}:{settings.stock_api_port}/api"
        self.batch_size = settings.stock_batch_size

    async def fetch_all_stock_info(self):
        """
        获取A股股票基本信息并同步到数据库
        每隔8小时执行一次
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
            logger.info("✓ A股股票信息同步完成！")
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
            async with httpx.AsyncClient(timeout=3000.0) as client:
                response = await client.post(
                    f"{self.api_base_url}/stocks/query",
                    json={
                        "statuses": ["LISTED"],
                        "exchanges": ["SH", "SZ"]
                    },
                    headers={"Content-Type": "application/json"}
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
        从数据源获取所有A股股票基本信息

        Returns:
            List[Dict]: 股票信息列表
        """
        try:
            # 在异步环境中运行同步的akshare调用
            loop = asyncio.get_event_loop()

            # 使用更稳定的接口：获取A股股票代码和名称
            # 这个接口相对简单，更不容易出现网络问题
            df = await loop.run_in_executor(None, ak.stock_info_a_code_name)

            if df is None or df.empty:
                logger.warning("未获取到A股数据")
                return []

            stocks = []
            for _, row in df.iterrows():
                try:
                    # akshare返回的列名: code(代码), name(名称)
                    code = str(row.get("code", ""))
                    name = str(row.get("name", ""))

                    if not code or not name:
                        continue

                    # 判断交易所：6开头为上交所(SH)，0或3开头为深交所(SZ)
                    if code.startswith("6"):
                        exchange = "SH"
                    elif code.startswith(("0", "3")):
                        exchange = "SZ"
                    else:
                        continue  # 跳过其他市场的股票

                    stocks.append({
                        "stockCode": code,
                        "stockName": name,
                        "companyName": name,  # akshare基础数据不包含完整公司名称，使用简称
                        "listingDate": "2000-01-01",  # akshare基础接口不提供上市日期，使用默认值
                        "industry": "未分类"  # akshare基础接口不提供行业信息，使用默认值
                    })

                except Exception as e:
                    logger.warning(f"解析股票数据失败: {row}, 错误: {e}")
                    continue

            logger.info(f"成功解析 {len(stocks)} 支A股股票信息")
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

        async with httpx.AsyncClient(timeout=6000.0) as client:
            for i in range(batches):
                start_idx = i * self.batch_size
                end_idx = min((i + 1) * self.batch_size, total)
                batch = stocks[start_idx:end_idx]

                logger.info(f"正在插入第 {i+1}/{batches} 批，共 {len(batch)} 条记录...")

                try:
                    response = await client.post(
                        f"{self.api_base_url}/stocks/batch",
                        json=batch,
                        headers={"Content-Type": "application/json"}
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
