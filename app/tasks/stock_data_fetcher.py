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

    async def fetch_all_stock_info(self):
        """
        获取A股股票基本信息并同步到数据库
        每天凌晨00:00执行一次

        流程：
        1. 查询数据库中已存在的股票
        2. 从数据源获取所有A股股票信息
        3. 比对差异，找出需要插入的股票
        4. 分批插入新股票
        5. 更新所有股票的详细信息（股价、市值等）
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

            # 5. 更新所有股票的详细信息
            logger.info("\n" + "=" * 80)
            logger.info("开始更新股票详细信息...")
            logger.info("=" * 80)
            await self.update_all_stock_details()

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
                        "statuses": ["LISTED"],
                        "exchanges": ["SH", "SZ", "BJ"]
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
                        # "companyName": name,  # akshare基础数据不包含完整公司名称，使用简称
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

    async def _fetch_individual_stock_info(self, stock_code: str) -> Optional[Dict]:
        """
        从数据源获取个股详细信息
        使用 akshare 的 stock_individual_info_em 接口

        Args:
            stock_code: 股票代码

        Returns:
            Dict: 个股详细信息，包含：
                - 最新股价 (latestPrice)
                - 股票代码 (stockCode)
                - 股票简称 (stockName)
                - 总股本 (totalShares)
                - 流通股 (circulatingShares)
                - 总市值 (totalMarketCap)
                - 流通市值 (circulatingMarketCap)
                - 行业 (industry)
                - 上市时间 (listingDate)
        """
        try:
            loop = asyncio.get_event_loop()
            # 调用 akshare 的 stock_individual_info_em 接口
            df = await loop.run_in_executor(
                None, ak.stock_individual_info_em, stock_code
            )

            if df is None or df.empty:
                logger.warning(f"未获取到股票 {stock_code} 的详细信息")
                return None

            # 将 DataFrame 转换为字典，方便提取信息
            info_dict = dict(zip(df["item"], df["value"]))

            # 提取需要的字段
            stock_info = {
                "stockCode": stock_code,
                "stockName": info_dict.get("股票简称", ""),
                "latestPrice": self._parse_float(info_dict.get("股价", "0")),
                "totalShares": self._parse_float(info_dict.get("总股本", "0")),
                "circulatingShares": self._parse_float(info_dict.get("流通股", "0")),
                "totalMarketCap": self._parse_float(info_dict.get("总市值", "0")),
                "circulatingMarketCap": self._parse_float(
                    info_dict.get("流通市值", "0")
                ),
                "industry": info_dict.get("行业", "未分类"),
                "listingDate": info_dict.get("上市时间", "2000-01-01"),
            }

            return stock_info

        except Exception as e:
            logger.warning(f"获取股票 {stock_code} 详细信息失败: {e}")
            return None

    def _parse_float(self, value: str) -> float:
        """
        解析字符串为浮点数

        Args:
            value: 字符串值

        Returns:
            float: 浮点数
        """
        try:
            # 移除可能的单位（亿、万等）
            value = str(value).replace("亿", "").replace("万", "").replace(",", "")
            return float(value) if value and value != "-" else 0.0
        except (ValueError, AttributeError):
            return 0.0

    def _compare_stock_info(self, db_stock: Dict, api_stock: Dict) -> bool:
        """
        比对数据库股票信息和 API 获取的股票信息
        检查关键字段是否有变化

        Args:
            db_stock: 数据库中的股票信息
            api_stock: API 获取的股票信息

        Returns:
            bool: True 表示有变化需要更新，False 表示无变化
        """
        # 需要比对的字段
        fields_to_compare = [
            ("latestPrice", "latestPrice"),
            ("totalShares", "totalShares"),
            ("circulatingShares", "circulatingShares"),
            ("totalMarketCap", "totalMarketCap"),
            ("circulatingMarketCap", "circulatingMarketCap"),
            ("industry", "industry"),
            ("listingDate", "listingDate"),
        ]

        for db_field, api_field in fields_to_compare:
            db_value = db_stock.get(db_field)
            api_value = api_stock.get(api_field)

            # 对于数值类型，使用浮点数比较（允许小误差）
            if isinstance(api_value, (int, float)):
                db_value = float(db_value) if db_value else 0.0
                api_value = float(api_value) if api_value else 0.0
                if abs(db_value - api_value) > 0.01:  # 允许 0.01 的误差
                    logger.debug(
                        f"字段 {db_field} 有变化: {db_value} -> {api_value}"
                    )
                    return True
            else:
                # 字符串类型直接比较
                if str(db_value) != str(api_value):
                    logger.debug(
                        f"字段 {db_field} 有变化: {db_value} -> {api_value}"
                    )
                    return True

        return False

    async def _update_stock_info(self, stock_id: int, stock_code: str, stock_info: Dict):
        """
        更新股票详细信息

        Args:
            stock_id: 股票ID
            stock_code: 股票代码
            stock_info: 股票信息
        """
        try:
            # 只提取需要更新的字段
            update_data = {
                "listingDate": stock_info.get("listingDate"),
                "latestPrice": stock_info.get("latestPrice"),
                "totalShares": stock_info.get("totalShares"),
                "circulatingShares": stock_info.get("circulatingShares"),
                "totalMarketCap": stock_info.get("totalMarketCap"),
                "circulatingMarketCap": stock_info.get("circulatingMarketCap"),
                "industry": stock_info.get("industry"),
            }

            logger.debug(f"准备更新股票 {stock_code} (ID: {stock_id}) 的信息: {update_data}")

            async with httpx.AsyncClient(timeout=None) as client:
                # 调用更新接口 PUT /api/stocks/{id}
                response = await client.put(
                    f"{self.api_base_url}/stocks/{stock_id}",
                    json=update_data,
                    headers=self.headers,
                )
                print(update_data)
                response.raise_for_status()

                result = response.json()
                if result.get("code") == 200:
                    logger.info(f"✓ 股票 {stock_code} (ID: {stock_id}) 信息更新成功")
                else:
                    logger.error(
                        f"✗ 股票 {stock_code} (ID: {stock_id}) 信息更新失败: {result.get('message')}"
                    )

        except httpx.HTTPError as e:
            logger.error(f"✗ 股票 {stock_code} (ID: {stock_id}) 更新接口请求失败: {e}")
        except Exception as e:
            logger.error(f"✗ 股票 {stock_code} (ID: {stock_id}) 更新时发生错误: {e}")

    async def update_all_stock_details(self):
        """
        更新所有股票的详细信息
        1. 查询数据库中的所有股票
        2. 遍历股票列表，获取每只股票的详细信息
        3. 比对字段，如果有变化则更新
        """
        logger.info("=" * 80)
        logger.info("开始更新股票详细信息...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中的所有股票
            logger.info("📊 步骤1: 查询数据库中的所有股票...")
            all_stocks = await self._query_existing_stocks()
            logger.info(f"✓ 查询到 {len(all_stocks)} 支股票")

            if not all_stocks:
                logger.warning("数据库中没有股票，跳过更新")
                return

            # 2. 遍历股票列表，获取详细信息并更新
            logger.info("\n📊 步骤2: 遍历股票列表，获取详细信息并更新...")
            logger.info(
                f"批次控制: 每 {settings.stock_update_batch_size} 条暂停 {settings.stock_update_batch_pause} 秒"
            )
            update_count = 0
            skip_count = 0
            error_count = 0

            for i, db_stock in enumerate(all_stocks):
                stock_id = db_stock.get("id")
                stock_code = db_stock.get("stockCode")
                stock_name = db_stock.get("stockName", "")

                try:
                    logger.info(
                        f"\n处理 [{i + 1}/{len(all_stocks)}] {stock_code} {stock_name}"
                    )

                    # 检查是否有股票ID
                    if not stock_id:
                        logger.warning(f"✗ 跳过股票 {stock_code}，缺少股票ID")
                        error_count += 1
                        continue

                    # 获取个股详细信息
                    api_stock_info = await self._fetch_individual_stock_info(
                        stock_code
                    )

                    if not api_stock_info:
                        logger.warning(f"✗ 跳过股票 {stock_code}，无法获取详细信息")
                        skip_count += 1
                        continue

                    # 比对字段
                    has_changes = self._compare_stock_info(db_stock, api_stock_info)

                    if has_changes:
                        logger.info(f"✓ 股票 {stock_code} 信息有变化，准备更新...")
                        await self._update_stock_info(stock_id, stock_code, api_stock_info)
                        update_count += 1
                    else:
                        logger.debug(f"- 股票 {stock_code} 信息无变化")
                        skip_count += 1

                    # 避免请求过快，稍作延迟
                    await asyncio.sleep(settings.stock_update_item_delay)

                    # 每处理 batch_size 条股票后暂停
                    if (i + 1) % settings.stock_update_batch_size == 0 and (i + 1) < len(all_stocks):
                        logger.info(
                            f"\n⏸️  已处理 {i + 1} 条，暂停 {settings.stock_update_batch_pause} 秒..."
                        )
                        logger.info(
                            f"当前进度: 更新 {update_count} 支，跳过 {skip_count} 支，错误 {error_count} 支"
                        )
                        await asyncio.sleep(settings.stock_update_batch_pause)
                        logger.info("⏯️  继续处理...")

                except Exception as e:
                    logger.error(f"✗ 处理股票 {stock_code} 时发生错误: {e}")
                    error_count += 1
                    continue

            logger.info("\n" + "=" * 80)
            logger.info(
                f"✓ 股票详细信息更新完成！更新 {update_count} 支，跳过 {skip_count} 支，错误 {error_count} 支"
            )
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"股票详细信息更新失败: {e}", exc_info=True)
            raise
