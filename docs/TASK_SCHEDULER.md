# 调度任务使用说明

## 概述

本系统提供了股票数据的自动同步和更新功能，包括：
1. **股票基本信息同步**：从数据源获取A股股票列表，同步到本地数据库
2. **股票详细信息更新**：获取每只股票的最新股价、市值等详细信息，并更新到数据库

## 自动调度

### 调度时间
- **执行频率**：每天凌晨 00:00 自动执行
- **执行内容**：
  1. 同步A股股票基本信息
  2. 更新所有股票的详细信息

### 调度配置

可以通过环境变量自定义调度时间，在 `.env` 文件中配置：

```bash
# 调度时间配置
STOCK_FETCH_SCHEDULE_HOUR=0          # 小时（24小时制，0-23）
STOCK_FETCH_SCHEDULE_MINUTE=0        # 分钟（0-59）
STOCK_FETCH_SCHEDULE_DAY_OF_WEEK=*   # 星期几（*=每天，mon-fri=工作日）
```

### 启动自动调度

运行主服务即可启动自动调度：

```bash
python3 app/main.py
```

## 手动执行

### 方式一：使用交互式脚本（推荐）

```bash
# 运行交互式任务菜单
./run_task.sh

# 或直接运行
python3 scripts/run_tasks.py
```

交互式菜单提供以下选项：
1. **执行股票基本信息同步任务**
   - 从数据源获取A股股票列表
   - 比对数据库，插入新股票
   - 更新所有股票的详细信息

2. **仅执行股票详细信息更新任务**
   - 获取每只股票的最新股价、市值等信息
   - 比对数据库，更新变化的字段

### 方式二：直接调用（用于脚本集成）

```python
import asyncio
from app.tasks.stock_data_fetcher import StockDataFetcher

async def run_task():
    fetcher = StockDataFetcher()

    # 执行完整同步（包含基本信息和详细信息）
    await fetcher.fetch_all_stock_info()

    # 或仅更新详细信息
    # await fetcher.update_all_stock_details()

asyncio.run(run_task())
```

## 任务详情

### 1. 股票基本信息同步任务

**功能**：
- 从 akshare 数据源获取所有A股股票列表
- 查询本地数据库中已存在的股票
- 比对差异，插入新上市的股票
- 执行完成后自动触发详细信息更新

**执行流程**：
```
1. 查询数据库中已存在的股票
2. 从数据源获取所有A股股票信息
3. 比对差异，找出需要插入的股票
4. 分批插入新股票（每批1000条）
5. 更新所有股票的详细信息
```

### 2. 股票详细信息更新任务

**功能**：
- 查询数据库中的所有股票
- 遍历每只股票，调用 akshare 的 `stock_individual_info_em` 接口获取详细信息
- 比对以下字段，如有变化则更新：
  - 最新股价 (latestPrice)
  - 总股本 (totalShares)
  - 流通股 (circulatingShares)
  - 总市值 (totalMarketCap)
  - 流通市值 (circulatingMarketCap)
  - 行业 (industry)
  - 上市时间 (listingDate)

**执行流程**：
```
1. 查询数据库中的所有股票
2. 遍历股票列表
   a. 调用 akshare 获取个股详细信息
   b. 比对字段是否有变化
   c. 如有变化，调用更新接口
3. 统计更新结果
```

## 更新接口

股票详细信息的更新接口位于：

```
PUT /api/stocks/{id}
```

**路径参数**：
- `id`: 股票ID（从数据库查询结果中获取）

**请求头**：
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer {token}"
}
```

**请求体示例**（仅包含需要更新的字段）：
```json
{
  "listingDate": "1991-04-03",
  "latestPrice": 12.34,
  "totalShares": 1937041.1584,
  "circulatingShares": 1937041.1584,
  "totalMarketCap": 239149.70,
  "circulatingMarketCap": 239149.70,
  "industry": "银行"
}
```

**注意**：
- 使用股票ID而不是股票代码作为路径参数
- 只发送需要更新的7个字段
- 所有字段均为可选

## 日志

所有任务执行日志会输出到控制台和日志文件，可以通过以下方式查看：

```bash
# 查看实时日志
tail -f logs/quant_trade.log

# 搜索特定股票的日志
grep "000001" logs/quant_trade.log
```

## 性能优化

### 批量处理
- 新股票插入采用批量处理，默认每批1000条
- 可通过环境变量 `STOCK_BATCH_SIZE` 调整批次大小

### 请求延迟和批次控制
- 为避免接口请求过快，在批次之间和股票遍历时添加了延迟
- **批量插入**：每批之间延迟 0.5 秒
- **详细信息更新**：
  - 每只股票之间延迟：0.2 秒（可通过 `STOCK_UPDATE_ITEM_DELAY` 调整）
  - 每处理 100 条股票暂停：300 秒 / 5 分钟（可通过 `STOCK_UPDATE_BATCH_PAUSE` 调整）
  - 批次大小：100 条（可通过 `STOCK_UPDATE_BATCH_SIZE` 调整）

### 批次控制配置
可以通过环境变量自定义批次控制参数：

```bash
# 股票更新批次控制
STOCK_UPDATE_BATCH_SIZE=100        # 每批处理数量
STOCK_UPDATE_BATCH_PAUSE=300       # 每批之间暂停秒数（5分钟=300秒）
STOCK_UPDATE_ITEM_DELAY=0.2        # 每只股票之间的延迟秒数
```

**示例**：
- 有 5000 支股票需要更新
- 每批 100 条，共 50 批
- 每批之间暂停 5 分钟
- 总耗时约：5000 × 0.2 秒 + 49 × 300 秒 ≈ 1000 秒 + 14700 秒 ≈ 4.35 小时

### 错误处理
- 单只股票获取失败不会中断整个流程
- 所有错误都会被记录到日志中
- 任务结束时会统计成功、跳过和错误的数量

## 故障排查

### 常见问题

1. **akshare 接口调用失败**
   - 检查网络连接
   - 确认 akshare 版本是否最新：`pip install -U akshare`
   - 查看具体错误信息

2. **数据库连接失败**
   - 检查配置文件中的 API 地址和端口
   - 确认 API 服务是否正常运行
   - 检查 token 是否有效

3. **任务执行缓慢**
   - 调整批次大小（减小 `STOCK_BATCH_SIZE`）
   - 增加请求延迟，避免接口限流
   - 检查网络状况

## 注意事项

⚠️ **重要提示**：
1. 首次执行会同步所有A股股票，耗时较长（约30分钟-1小时）
2. 详细信息更新会遍历所有股票，建议在低峰期执行
3. 确保 API 服务正常运行，否则任务会失败
4. 定期检查日志，确保任务正常执行
