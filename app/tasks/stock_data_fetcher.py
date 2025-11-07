"""
股票基本信息获取任务
获取A股的基本信息并同步到本地数据库
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

import tushare as ts
import httpx
import pandas as pd

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
        1. 调用后端查询接口（1次） - 获取已存在的股票代码
        2. 调用 Tushare 股票列表接口（1次） - 获取所有A股股票信息
        3. 对比差异，找出需要插入的新股票
        4. 调用后端批量插入接口（若干次） - 只插入新股票
        """
        logger.info("=" * 80)
        logger.info("开始同步股票基本信息...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 查询数据库中已存在的股票代码（只查代码，减少数据传输）
            logger.info("📊 步骤1: 查询数据库中已存在的股票代码...")
            existing_codes = await self._query_existing_stock_codes()
            logger.info(f"✓ 数据库中已存在 {len(existing_codes)} 支股票")

            # 2. 从 Tushare Pro 获取所有A股股票信息
            logger.info("\n📊 步骤2: 从 Tushare Pro 获取所有A股股票信息...")
            all_stocks = await self._fetch_a_share_info()
            logger.info(f"✓ 从 Tushare Pro 获取到 {len(all_stocks)} 支A股股票")

            # 3. 对比差异，找出需要插入的新股票
            logger.info("\n📊 步骤3: 对比差异，筛选需要插入的新股票...")
            stocks_to_insert = [
                stock for stock in all_stocks
                if stock["stockCode"] not in existing_codes
            ]
            logger.info(f"✓ 发现 {len(stocks_to_insert)} 支新股票需要插入")

            # 4. 分批插入新股票
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

    async def _query_existing_stock_codes(self) -> set:
        """
        查询数据库中已存在的股票代码（只查代码，不查全部字段）

        Returns:
            set: 已存在的股票代码集合
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
                    stocks = result.get("data", [])
                    # 只提取股票代码到集合中，释放完整数据
                    return {stock["stockCode"] for stock in stocks}
                else:
                    logger.error(f"查询股票失败: {result.get('message')}")
                    return set()

        except httpx.HTTPError as e:
            logger.error(f"查询股票接口请求失败: {e}")
            return set()
        except Exception as e:
            logger.error(f"查询股票时发生错误: {e}", exc_info=True)
            return set()

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
            # 获取所有状态
            df = await loop.run_in_executor(
                None,
                lambda: self.pro.stock_basic(
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

    async def fetch_all_company_info(self):
        """
        获取全量上市公司基本信息并同步到数据库
        每周末凌晨1:00执行一次

        流程：
        1. 从 Tushare Pro 分批获取全量公司基本信息（每次4500条）
        2. 分批调用后端批量插入接口（每批1000条）
        """
        logger.info("=" * 80)
        logger.info("开始同步上市公司基本信息...")
        logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        try:
            # 1. 从 Tushare Pro 获取全量公司基本信息
            logger.info("\n📊 步骤1: 从 Tushare Pro 获取全量公司基本信息...")
            all_companies = await self._fetch_all_company_info_from_tushare()
            logger.info(f"✓ 从 Tushare Pro 获取到 {len(all_companies)} 家公司信息")

            # 2. 分批调用后端批量插入接口
            if all_companies:
                logger.info(f"\n📊 步骤2: 分批插入公司信息（每批1000条）...")
                await self._batch_upsert_companies(all_companies)
            else:
                logger.info("\n✓ 没有公司信息需要同步")

            self.last_fetch_time = datetime.now()
            logger.info("\n" + "=" * 80)
            logger.info("✓ 上市公司基本信息同步完成！")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"公司信息同步失败: {e}", exc_info=True)
            raise

    async def _fetch_all_company_info_from_tushare(self) -> List[Dict]:
        """
        从 Tushare Pro 分批获取全量公司基本信息
        每次请求4500条，直到全部获取

        Returns:
            List[Dict]: 公司信息列表
        """
        try:
            loop = asyncio.get_event_loop()
            all_companies = []
            offset = 0
            limit = 4500  # 每次请求4500条

            while True:
                logger.info(f"正在获取第 {offset} - {offset + limit} 条公司信息...")

                # 调用 Tushare Pro 的 stock_company 接口
                # 注意：必须包含 com_name 和 com_id 字段
                current_offset = offset
                current_limit = limit
                df = await loop.run_in_executor(
                    None,
                    lambda: self.pro.stock_company(
                        fields='ts_code,com_name,com_id,exchange,chairman,manager,secretary,reg_capital,setup_date,province,city,introduction,website,email,office,employees,main_business,business_scope',
                        limit=current_limit,
                        offset=current_offset
                    )
                )

                if df is None or df.empty:
                    logger.info(f"✓ 已获取全部公司信息，共 {len(all_companies)} 条")
                    break

                # 解析数据
                for _, row in df.iterrows():
                    try:
                        ts_code = str(row.get("ts_code", ""))
                        if not ts_code:
                            continue

                        # 处理日期格式：YYYYMMDD -> YYYY-MM-DD
                        setup_date = str(row.get("setup_date", ""))
                        if setup_date and len(setup_date) == 8:
                            setup_date = f"{setup_date[:4]}-{setup_date[4:6]}-{setup_date[6:]}"
                        else:
                            setup_date = None

                        # 直接从接口返回的数据中获取公司名称和ID
                        com_name = str(row.get("com_name", "")) if pd.notna(row.get("com_name")) else ts_code
                        com_id = str(row.get("com_id", "")) if pd.notna(row.get("com_id")) else ts_code

                        # 处理数值类型字段（可能为 NaN）
                        reg_capital = row.get("reg_capital")
                        reg_capital = float(reg_capital) if pd.notna(reg_capital) else None

                        employees = row.get("employees")
                        employees = int(employees) if pd.notna(employees) else None

                        # 构建公司信息字典
                        company_info = {
                            "stockCode": ts_code,
                            "comName": com_name,
                            "comId": com_id,
                            "exchange": str(row.get("exchange", "")) if pd.notna(row.get("exchange")) else "",
                            "chairman": str(row.get("chairman", "")) if pd.notna(row.get("chairman")) else "",
                            "manager": str(row.get("manager", "")) if pd.notna(row.get("manager")) else None,
                            "secretary": str(row.get("secretary", "")) if pd.notna(row.get("secretary")) else None,
                            "regCapital": reg_capital,
                            "setupDate": setup_date,
                            "province": str(row.get("province", "")) if pd.notna(row.get("province")) else None,
                            "city": str(row.get("city", "")) if pd.notna(row.get("city")) else None,
                            "introduction": str(row.get("introduction", "")) if pd.notna(row.get("introduction")) else None,
                            "website": str(row.get("website", "")) if pd.notna(row.get("website")) else None,
                            "email": str(row.get("email", "")) if pd.notna(row.get("email")) else None,
                            "office": str(row.get("office", "")) if pd.notna(row.get("office")) else None,
                            "employees": employees,
                            "mainBusiness": str(row.get("main_business", "")) if pd.notna(row.get("main_business")) else None,
                            "businessScope": str(row.get("business_scope", "")) if pd.notna(row.get("business_scope")) else None,
                        }

                        all_companies.append(company_info)

                    except Exception as e:
                        logger.warning(f"解析公司数据失败: {row}, 错误: {e}")
                        continue

                logger.info(f"✓ 获取到 {len(df)} 条记录，累计 {len(all_companies)} 条")

                # 如果返回的数据少于请求的数量，说明已经是最后一批
                if len(df) < limit:
                    logger.info(f"✓ 已获取全部公司信息，共 {len(all_companies)} 条")
                    break

                # 更新偏移量
                offset += limit

                # 避免请求过快
                await asyncio.sleep(1)

            return all_companies

        except Exception as e:
            logger.error(f"从 Tushare Pro 获取公司信息失败: {e}", exc_info=True)
            return []

    async def _batch_upsert_companies(self, companies: List[Dict]):
        """
        分批次批量插入/更新公司信息
        每批1000条

        Args:
            companies: 待插入的公司信息列表
        """
        total = len(companies)
        batch_size = 1000
        batches = (total + batch_size - 1) // batch_size  # 向上取整

        success_count = 0
        fail_count = 0

        async with httpx.AsyncClient(timeout=None) as client:
            for i in range(batches):
                start_idx = i * batch_size
                end_idx = min((i + 1) * batch_size, total)
                batch = companies[start_idx:end_idx]

                logger.info(f"正在插入第 {i+1}/{batches} 批公司信息，共 {len(batch)} 条记录...")

                try:
                    response = await client.post(
                        f"{self.api_base_url}/stock-companies/batch-upsert",
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
