# Quant Trade - 量化交易服务框架

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

一个轻量级的量化交易服务框架，采用异步架构，支持作为持续运行的后台服务。

## 🚀 特性

- **轻量级框架** - 最小化依赖，专注核心功能
- **服务架构** - 支持作为后台服务持续运行
- **异步设计** - 基于 asyncio 的异步任务调度
- **灵活配置** - 通过环境变量灵活配置
- **多种部署方式** - 支持直接运行、systemd、supervisor、Docker 等

## 🛠️ 技术栈

- **Python 3.8+** - 核心语言
- **asyncio** - 异步编程
- **Pydantic** - 配置管理和数据验证
- **Pandas / NumPy** - 数据分析

## 📁 项目结构

```
quant_trade/
├── app/                        # 应用主目录
│   ├── __init__.py
│   ├── main.py                 # 服务入口
│   ├── core/                   # 核心模块
│   │   ├── __init__.py
│   │   └── config.py           # 配置管理
│   └── utils/                  # 工具模块
│       ├── __init__.py
│       └── logger.py           # 日志工具
├── scripts/                    # 脚本目录
│   ├── service_manager.py      # 服务管理脚本
│   └── README.md
├── deployment/                 # 部署配置
│   ├── quant-trade.service     # systemd 配置
│   ├── supervisor.conf         # supervisor 配置
│   ├── com.quanttrade.service.plist  # launchd 配置 (macOS)
│   └── README.md
├── logs/                       # 日志目录
├── .env                        # 环境变量配置
├── .env.example                # 环境变量示例
├── pyproject.toml              # 项目配置
├── Dockerfile                  # Docker 镜像
├── docker-compose.yml          # Docker Compose
├── QUICKSTART.md               # 快速启动指南
└── README.md                   # 项目说明
```

## ⚡ 快速开始

### 1. 环境要求

- Python 3.8+

### 2. 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/quant_trade.git
cd quant_trade

# 安装依赖
pip install -e .

# 或安装开发依赖
pip install -e ".[dev]"
```

### 3. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑配置
nano .env
```

主要配置项：

```bash
# 项目信息
PROJECT_NAME="Quant Trade"
VERSION="1.0.0"

# 交易配置
TRADING_ENABLED=false        # 是否启用交易
SIMULATION_MODE=true         # 模拟模式

# 数据源
DATA_PROVIDER=akshare        # 数据提供者

# 日志级别
LOG_LEVEL=INFO

# 调度间隔（秒）
MARKET_MONITOR_INTERVAL=60          # 市场监控间隔
STRATEGY_EXECUTION_INTERVAL=300     # 策略执行间隔
HEALTH_CHECK_INTERVAL=30            # 健康检查间隔
```

### 4. 启动服务

#### 方式 1: 使用服务管理脚本（推荐）

```bash
# 启动服务
python scripts/service_manager.py start

# 查看状态
python scripts/service_manager.py status

# 查看日志
python scripts/service_manager.py logs

# 停止服务
python scripts/service_manager.py stop

# 重启服务
python scripts/service_manager.py restart
```

#### 方式 2: 直接运行

```bash
# 前台运行
python -m app.main

# 后台运行
nohup python -m app.main > logs/service.log 2>&1 &
```

#### 方式 3: 使用 Docker

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

### 5. 验证

查看日志确认服务启动：

```bash
tail -f logs/service.log
```

你应该看到：

```
============================================================
🚀 Quant Trade 服务启动
📊 模拟模式: True
🔄 交易启用: False
============================================================
📈 市场监控任务已启动
🎯 策略执行任务已启动
💚 健康检查任务已启动
```

## 📚 详细文档

- [快速启动指南](QUICKSTART.md) - 详细的启动步骤
- [部署文档](deployment/README.md) - 各种部署方式说明
- [脚本文档](scripts/README.md) - 服务管理脚本使用

## 🔧 开发指南

### 服务架构

服务包含三个主要的异步任务循环：

1. **市场监控循环** (`_market_monitor_loop`)
   - 定时获取市场数据
   - 监控市场状态
   - 可配置执行间隔

2. **策略执行循环** (`_strategy_execution_loop`)
   - 运行交易策略
   - 生成交易信号
   - 执行交易指令

3. **健康检查循环** (`_health_check_loop`)
   - 检查系统状态
   - 监控服务健康度

### 添加业务逻辑

在 `app/main.py` 中的对应方法添加你的业务逻辑：

```python
async def _market_monitor_loop(self):
    """在这里添加市场监控逻辑"""
    while self.running:
        # 你的代码
        await asyncio.sleep(settings.market_monitor_interval)

async def _strategy_execution_loop(self):
    """在这里添加策略执行逻辑"""
    while self.running:
        # 你的代码
        await asyncio.sleep(settings.strategy_execution_interval)
```

### 添加新模块

项目结构简洁，你可以根据需要添加：

```bash
app/
├── strategies/       # 交易策略
├── data/            # 数据处理
├── brokers/         # 经纪商接口
└── ...              # 其他模块
```

## 🚀 生产部署

### systemd (Linux)

```bash
sudo cp deployment/quant-trade.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable quant-trade
sudo systemctl start quant-trade
```

### Supervisor

```bash
sudo cp deployment/supervisor.conf /etc/supervisor/conf.d/quant-trade.conf
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start quant-trade
```

### launchd (macOS)

```bash
cp deployment/com.quanttrade.service.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.quanttrade.service.plist
launchctl start com.quanttrade.service
```

详见 [deployment/README.md](deployment/README.md)

## 🛠️ 常见问题

### 服务无法启动

1. 检查 Python 环境：`which python3`
2. 检查依赖安装：`pip list`
3. 查看详细错误：`python -m app.main`

### 权限错误

```bash
chmod +x scripts/service_manager.py
chmod +x app/main.py
```

### 查看日志

```bash
# 实时查看
tail -f logs/service.log

# 查看最近的日志
python scripts/service_manager.py logs
```

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情

## 🛣️ 开发计划

- [ ] 数据采集模块
- [ ] 策略框架
- [ ] 回测引擎
- [ ] 风险管理
- [ ] 实盘交易接口
- [ ] Web 管理界面

## ⭐ Star History

如果这个项目对你有帮助，请给它一个星星！

---

**注意**：这是一个基础框架，需要根据实际业务需求添加具体的交易逻辑。
