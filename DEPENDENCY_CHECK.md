# 依赖检查报告

## 📦 当前项目依赖

### 核心依赖 (requirements)

从 `pyproject.toml` 中定义的生产环境依赖：

```toml
dependencies = [
    # 数据验证和设置
    "pydantic>=2.5.0",           # 数据验证
    "pydantic-settings>=2.1.0",  # 设置管理（从环境变量加载配置）

    # 数据处理
    "pandas>=2.0.0",             # 数据分析和处理
    "numpy>=1.24.0",             # 数值计算

    # 环境配置
    "python-dotenv>=1.0.0",      # 加载 .env 文件
]
```

### 开发依赖 (dev)

```toml
dev = [
    # 测试
    "pytest==7.4.3",             # 测试框架
    "pytest-asyncio==0.21.1",    # 异步测试支持

    # 代码质量
    "black==23.11.0",            # 代码格式化
    "isort==5.13.2",             # 导入排序
    "flake8>=6.0.0",             # 代码检查

    # 开发工具
    "ipython>=8.0.0",            # 交互式 Python
    "jupyter>=1.0.0",            # Jupyter Notebook
]
```

### 生产依赖 (prod)

```toml
prod = [
    # 生产环境特定依赖（目前为空）
]
```

---

## ✅ 依赖分析

### 必要依赖 ✓

1. **pydantic + pydantic-settings** ✓
   - 用途：配置管理 (`app/core/config.py`)
   - 状态：正在使用
   - 建议：保留

2. **python-dotenv** ✓
   - 用途：加载 `.env` 文件
   - 状态：pydantic-settings 依赖它
   - 建议：保留

3. **pandas + numpy** ⚠️
   - 用途：数据分析和处理
   - 状态：当前未使用，但量化交易必需
   - 建议：保留（后续会用到）

### 开发依赖 ✓

所有开发依赖都是标准的 Python 开发工具，建议保留。

---

## 🔄 已移除的依赖

以下依赖在优化时已移除（不再需要）：

```toml
# Web 框架（已移除）
"fastapi>=0.104.1"           # FastAPI 框架
"uvicorn[standard]>=0.24.0"  # ASGI 服务器

# 数据库（已移除）
"sqlalchemy[asyncio]>=2.0.23"    # ORM
"asyncpg>=0.29.0"                # PostgreSQL 驱动
"psycopg2-binary>=2.9.0"         # PostgreSQL 驱动（备用）
"alembic>=1.12.0"                # 数据库迁移

# 生产环境（已移除）
"gunicorn>=21.0.0"               # WSGI 服务器
```

---

## 🎯 依赖使用情况

### 当前代码中的依赖使用

| 依赖 | 使用位置 | 状态 |
|------|---------|------|
| pydantic-settings | `app/core/config.py` | ✅ 使用中 |
| python-dotenv | 由 pydantic-settings 调用 | ✅ 使用中 |
| pandas | 未使用 | ⚠️ 预留 |
| numpy | 未使用 | ⚠️ 预留 |
| asyncio | `app/main.py` | ✅ 使用中（标准库）|
| logging | `app/utils/logger.py` | ✅ 使用中（标准库）|
| signal | `app/main.py` | ✅ 使用中（标准库）|
| sys | `app/main.py`, `app/utils/logger.py` | ✅ 使用中（标准库）|

---

## 📝 建议

### 1. 当前依赖配置 ✅ 合理

当前的依赖配置非常精简，只保留了必要的包：
- ✅ 配置管理相关包（pydantic）
- ✅ 数据处理相关包（pandas, numpy）
- ✅ 开发工具包

### 2. 可选的额外依赖

根据后续开发需求，可能需要添加：

**数据获取：**
```toml
"akshare>=1.11.0"        # A股数据
"yfinance>=0.2.0"        # Yahoo Finance 数据
"tushare>=1.3.0"         # Tushare 数据
```

**技术指标：**
```toml
"ta-lib>=0.4.0"          # 技术分析库（需要系统依赖）
"pandas-ta>=0.3.0"       # Pandas 技术分析扩展
```

**交易执行：**
```toml
"ccxt>=4.0.0"            # 加密货币交易所接口
```

**性能优化：**
```toml
"numba>=0.58.0"          # JIT 编译加速
```

**数据存储（如需要）：**
```toml
"redis>=5.0.0"           # Redis 客户端
"pymongo>=4.0.0"         # MongoDB 客户端
```

### 3. 安装说明

**基础安装：**
```bash
pip install -e .
```

**开发环境：**
```bash
pip install -e ".[dev]"
```

**指定依赖版本：**
```bash
pip install -e . --no-deps
pip install pydantic==2.5.0 pydantic-settings==2.1.0
```

---

## 🔒 依赖锁定

### 建议使用 pip-tools 或 poetry 锁定依赖

**使用 pip-tools：**
```bash
# 安装 pip-tools
pip install pip-tools

# 生成 requirements.txt
pip-compile pyproject.toml

# 安装锁定的依赖
pip-sync
```

**使用 poetry：**
```bash
# 初始化 poetry
poetry init

# 添加依赖
poetry add pydantic pydantic-settings pandas numpy python-dotenv

# 安装
poetry install
```

---

## ⚠️ 注意事项

1. **Python 版本**：项目要求 Python 3.8+
2. **pandas/numpy**：虽然目前未使用，但量化交易几乎必然需要
3. **可选依赖**：根据实际需求添加，避免过度依赖
4. **依赖更新**：定期更新依赖以获取安全补丁

---

## 📊 依赖大小估算

安装所有核心依赖后的大小约：
- pydantic + pydantic-settings: ~5 MB
- pandas: ~20 MB
- numpy: ~15 MB
- python-dotenv: <1 MB

**总计约 40 MB**（不含开发依赖）

---

最后更新：2025-10-30
