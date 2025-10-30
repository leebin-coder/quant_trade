# 项目结构说明

## 当前项目结构

```
quant_trade/
├── app/                              # 应用主目录
│   ├── __init__.py                   # 空的初始化文件
│   ├── main.py                       # 服务主入口 (140+ 行)
│   ├── core/                         # 核心配置模块
│   │   ├── __init__.py               # 空的初始化文件
│   │   └── config.py                 # 配置管理 (34 行)
│   └── utils/                        # 工具模块
│       ├── __init__.py               # 空的初始化文件
│       └── logger.py                 # 日志工具 (18 行)
│
├── scripts/                          # 脚本目录
│   ├── service_manager.py            # 服务管理脚本 (启动/停止/重启/状态/日志)
│   └── README.md
│
├── deployment/                       # 部署配置
│   ├── quant-trade.service           # systemd 服务配置 (Linux)
│   ├── supervisor.conf               # Supervisor 配置
│   ├── com.quanttrade.service.plist  # launchd 配置 (macOS)
│   └── README.md                     # 部署文档
│
├── logs/                             # 日志目录 (运行时生成)
│
├── .env                              # 环境变量配置 (不提交到 git)
├── .env.example                      # 环境变量模板
├── pyproject.toml                    # 项目配置和依赖
├── Dockerfile                        # Docker 镜像配置
├── docker-compose.yml                # Docker Compose 配置
├── .dockerignore                     # Docker 忽略文件
├── .gitignore                        # Git 忽略文件
│
├── QUICKSTART.md                     # 快速启动指南
├── README.md                         # 项目说明文档
└── PROJECT_STRUCTURE.md              # 本文件
```

## 核心文件说明

### app/main.py
服务主入口，包含：
- `TradingService` 类：主服务类
- 三个异步任务循环：
  - `_market_monitor_loop()` - 市场监控
  - `_strategy_execution_loop()` - 策略执行
  - `_health_check_loop()` - 健康检查
- 优雅的启动/停止机制
- 信号处理（SIGINT, SIGTERM）

### app/core/config.py
配置管理，使用 Pydantic Settings：
- 项目基本信息
- 交易配置
- 数据源配置
- 日志配置
- 调度间隔配置

### app/utils/logger.py
日志工具，提供：
- 统一的日志格式
- 输出到 stdout
- 全局 logger 实例

### scripts/service_manager.py
服务管理脚本，支持：
- `start` - 启动服务
- `stop` - 停止服务
- `restart` - 重启服务
- `status` - 查看状态
- `logs` - 查看日志

## 代码统计

```
文件类型          文件数    代码行数
--------------------------------------
Python            6        ~200
Markdown          5        ~500
配置文件          8        ~150
--------------------------------------
总计             19        ~850
```

## 已删除的内容

为了保持项目简洁，已删除以下空的业务逻辑骨架：

- `app/strategies/` - 策略模块（4个空文件）
- `app/domain/` - 领域层（7个空文件）
- `app/application/` - 应用层（8个空文件）
- `app/infrastructure/` - 基础设施层（14个空文件）
- `app/api/` - API 层
- FastAPI 相关配置
- 数据库相关配置
- 不必要的脚本文件

## 依赖项

### 核心依赖
- `pydantic>=2.5.0` - 数据验证和配置管理
- `pydantic-settings>=2.1.0` - 设置管理
- `pandas>=2.0.0` - 数据分析
- `numpy>=1.24.0` - 数值计算
- `python-dotenv>=1.0.0` - 环境变量加载

### 开发依赖
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试
- `black` - 代码格式化
- `isort` - 导入排序
- `flake8` - 代码检查

## 如何添加新功能

### 1. 添加新的模块

在 `app/` 下创建新目录：

```bash
app/
├── strategies/        # 交易策略
├── data/             # 数据处理
├── brokers/          # 经纪商接口
└── ...
```

### 2. 添加新的配置项

在 `app/core/config.py` 的 `Settings` 类中添加：

```python
class Settings(BaseSettings):
    # 新的配置项
    new_config: str = Field("default", env="NEW_CONFIG")
```

然后在 `.env` 和 `.env.example` 中添加相应的环境变量。

### 3. 添加新的任务循环

在 `app/main.py` 的 `TradingService` 类中：

```python
async def _new_task_loop(self):
    """新的任务循环"""
    while self.running:
        try:
            # 你的逻辑
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"新任务出错: {e}")
```

然后在 `start()` 方法中启动：

```python
self.tasks = [
    asyncio.create_task(self._market_monitor_loop()),
    asyncio.create_task(self._strategy_execution_loop()),
    asyncio.create_task(self._health_check_loop()),
    asyncio.create_task(self._new_task_loop()),  # 添加这行
]
```

## 最佳实践

1. **保持简洁**：只添加真正需要的代码
2. **配置驱动**：使用环境变量控制行为
3. **异步优先**：使用 async/await 处理 I/O 操作
4. **日志记录**：在关键位置记录日志
5. **错误处理**：捕获并记录异常，避免服务崩溃

## 下一步

1. 实现具体的市场数据获取逻辑
2. 开发交易策略
3. 添加数据持久化（如需要）
4. 实现交易执行逻辑
5. 添加监控和告警
