 Quant Trade - 专业量化交易系统

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104%2B-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-13%2B-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

一个基于 FastAPI 和 AsyncSQLAlchemy 构建的专业量化交易系统，采用领域驱动设计(DDD)和清洁架构，支持多市场数据采集、策略回测和自动交易执行。

## 🚀 核心特性

### 📊 数据管理
- **多数据源支持**：集成 AKShare、YFinance 等数据提供商
- **异步数据采集**：高性能异步数据获取和存储
- **历史数据管理**：完整的股票、期货历史数据存储
- **实时行情**：支持实时行情数据订阅和推送

### 🤖 策略引擎
- **策略框架**：灵活的策略开发和回测框架
- **多策略支持**：趋势跟踪、均值回归、因子模型等
- **回测系统**：完整的策略回测和绩效分析
- **实时监控**：策略运行状态实时监控

### 🔄 交易执行
- **多券商支持**：模拟交易和实盘交易接口
- **风险控制**：多层次风险管理和资金管理
- **订单管理**：完整的订单生命周期管理
- **执行算法**：智能订单执行算法

### 🏗️ 系统架构
- **领域驱动设计**：清晰的分层架构和领域模型
- **异步架构**：基于 AsyncSQLAlchemy 的高性能异步处理
- **微服务就绪**：支持容器化部署和水平扩展
- **API 优先**：完整的 RESTful API 设计

## 🛠️ 技术栈

### 后端框架
- **FastAPI** - 高性能异步 Web 框架
- **SQLAlchemy 2.0** - 异步 ORM
- **Pydantic** - 数据验证和设置管理
- **Alembic** - 数据库迁移

### 数据库
- **PostgreSQL** - 主数据库
- **Redis** - 缓存和消息队列

### 量化分析
- **Pandas** - 数据分析
- **NumPy** - 数值计算
- **TA-Lib** - 技术指标计算

### 部署运维
- **Docker** - 容器化部署
- **Docker Compose** - 服务编排
- **Uvicorn** - ASGI 服务器

## 📁 项目结构
quant_trade/
├── app/ # 主应用目录
│ ├── api/ # API 表现层
│ │ └── routes/ # API 路由
│ ├── core/ # 核心配置
│ ├── domain/ # 领域层
│ │ ├── entities/ # 领域实体
│ │ └── services/ # 领域服务
│ ├── infrastructure/ # 基础设施层
│ │ ├── database/ # 数据库
│ │ ├── external/ # 外部服务
│ │ └── message_bus/ # 消息总线
│ ├── application/ # 应用层
│ │ ├── use_cases/ # 应用用例
│ │ └── schedulers/ # 任务调度
│ ├── strategies/ # 交易策略
│ └── utils/ # 工具函数
├── tests/ # 测试目录
├── scripts/ # 部署脚本
├── docker/ # Docker 配置
└── docs/ # 项目文档

text

## ⚡ 快速开始

### 环境要求

- Python 3.8+
- PostgreSQL 13+
- Redis 6+

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/leebin-coder/quant_trade.git
cd quant_trade
创建虚拟环境

bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
安装依赖

bash
pip install -r requirements/base.txt
环境配置

bash
cp .env.example .env
# 编辑 .env 文件，配置数据库连接等信息
启动服务

bash
python -m app.main
服务启动后访问：

主页: http://localhost:8000

API文档: http://localhost:8000/docs

健康检查: http://localhost:8000/api/health/health

Docker 部署
bash
# 使用 Docker Compose 启动所有服务
docker-compose -f docker/docker-compose.yml up -d

# 查看服务状态
docker-compose -f docker/docker-compose.yml ps
📚 使用指南
数据管理
bash
# 获取股票列表
curl http://localhost:8000/api/data/stocks

# 更新股票数据
curl -X POST http://localhost:8000/api/data/update/stocks
策略回测
bash
# 回测趋势跟踪策略
curl -X POST http://localhost:8000/api/strategies/backtest/trend_following \
  -H "Content-Type: application/json" \
  -d '{
    "symbols": ["000001", "000002"],
    "start_date": "2023-01-01",
    "end_date": "2023-12-31"
  }'
交易执行
bash
# 获取交易状态
curl http://localhost:8000/api/trading/status

# 提交订单
curl -X POST http://localhost:8000/api/trading/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "000001",
    "side": "BUY",
    "quantity": 100,
    "order_type": "MARKET"
  }'
🔧 开发指南
添加新的数据源
在 app/infrastructure/external/data_providers/ 创建新的数据提供者

实现 BaseDataProvider 接口

在领域服务中集成新的数据源

开发交易策略
在 app/strategies/ 创建策略类

继承 BaseStrategy 基类

实现 calculate_signals 和 backtest 方法

数据库迁移
bash
# 生成迁移脚本
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head
🤝 贡献指南
我们欢迎各种形式的贡献！请阅读我们的贡献指南：

Fork 本仓库

创建特性分支 (git checkout -b feature/AmazingFeature)

提交更改 (git commit -m 'Add some AmazingFeature')

推送到分支 (git push origin feature/AmazingFeature)

开启一个 Pull Request

📄 许可证
本项目采用 MIT 许可证 - 查看 LICENSE 文件了解详情。

🛣️ 开发路线图
完善数据采集模块

实现基础策略框架

开发回测引擎

集成实盘交易接口

添加风险管理模块

实现用户管理和权限控制

开发 Web 管理界面

支持分布式部署

📞 联系我们
项目主页: https://github.com/leebin-coder/quant_trade

问题反馈: GitHub Issues

🙏 致谢
感谢以下开源项目的贡献：

FastAPI

SQLAlchemy

AKShare

Pandas

⭐ 如果这个项目对你有帮助，请给它一个星星！

注意：本项目仍在积极开发中，API 可能会发生变化。建议在生产环境使用前进行充分测试。
