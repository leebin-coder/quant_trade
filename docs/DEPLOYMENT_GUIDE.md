# 部署指南

## 环境要求

- Docker & Docker Compose
- 网络访问（用于拉取 Python 依赖和 Baostock 数据）

## 快速开始

### 1. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置文件
nano .env
```

### 2. 关键配置项

#### 必须配置
```bash
# 股票 API 配置（后端服务地址）
STOCK_API_HOST=quant-gateway  # Docker 环境使用容器名
STOCK_API_PORT=8080
STOCK_API_TOKEN=your_token_here  # 替换为实际 token
```

#### 推荐配置
```bash
# 日线数据同步线程数（重要！）
STOCK_DAILY_MAX_WORKERS=2  # 推荐 2-3，不要超过 3
```

### 3. 构建和启动

```bash
# 构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

## 重要说明

### Baostock 服务器限制

由于 Baostock 服务器稳定性问题，**强烈建议**使用 2-3 个线程：

| 线程数 | 稳定性 | 速度 | 推荐度 |
|--------|--------|------|--------|
| 1 | ⭐⭐⭐⭐⭐ | ⭐ | ✅ 首次全量同步 |
| 2 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ✅✅ 日常增量同步（推荐） |
| 3 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 可接受 |
| 5+ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ 不推荐（大量错误） |

### 性能预期

以 5000 只股票为例：

- **1 线程**：约 4 小时，错误率 <1%
- **2 线程**：约 2 小时，错误率 5-10%
- **3 线程**：约 1.5 小时，错误率 10-15%
- **5+ 线程**：约 1 小时，错误率 >30%

## 常见问题

### Q1: 为什么会有很多网络接收错误？

A: 这是 Baostock 服务器的限制，不是代码问题。已经实现了：
- ✅ 登录锁（避免并发登录）
- ✅ 随机延迟（分散请求压力）
- ✅ 指数退避重试（最多重试 5 次）
- ✅ 请求间隔控制

即使有这些优化，Baostock 在高并发时仍然不稳定。**降低线程数是最有效的解决方案**。

### Q2: 如何查看同步进度？

```bash
# 实时查看日志
docker compose logs -f | grep -E "(进度|成功|失败)"

# 查看统计信息
docker compose logs | grep "股票日线数据同步完成"
```

### Q3: 某些股票同步失败怎么办？

失败的股票会在日志中标记为 `✗`。可以：

1. 查看失败股票列表：
```bash
docker compose logs | grep "✗"
```

2. 重新运行任务（会自动跳过已同步的股票）
3. 如果持续失败，可能是该股票数据源问题，可以忽略

### Q4: 首次全量同步建议

首次同步大量股票时：

```bash
# 修改 .env 文件
STOCK_DAILY_MAX_WORKERS=1  # 使用单线程确保稳定性

# 重启服务
docker compose restart
```

全量同步完成后，再改回 2-3 个线程用于日常增量同步。

## 调度说明

服务会自动按以下时间执行任务：

- **股票基础数据**：每天凌晨 0:00
- **公司信息**：每周末凌晨 1:00
- **交易日历**：每天凌晨 2:00
- **日线数据**：每天下午 4:00

可以在 `.env` 中修改这些时间。

## 监控和维护

### 查看服务状态

```bash
# 查看容器状态
docker compose ps

# 查看资源使用
docker stats

# 查看最近的日志
docker compose logs --tail=100
```

### 重启服务

```bash
# 重启所有服务
docker compose restart

# 重启指定服务
docker compose restart quant-python
```

### 停止服务

```bash
# 停止服务
docker compose stop

# 停止并删除容器
docker compose down
```

## 故障排查

### 服务无法启动

1. 检查配置文件：
```bash
cat .env | grep -v "^#"
```

2. 查看错误日志：
```bash
docker compose logs
```

### 无法连接后端 API

1. 检查网络连接：
```bash
docker network ls
docker network inspect quant_trade_python_default
```

2. 测试 API 连接：
```bash
docker compose exec quant-python curl http://quant-gateway:8080/health
```

### 大量 Baostock 错误

这是正常现象（参考 Q1）。解决方法：
1. **降低线程数到 2**
2. 等待重试机制自动处理
3. 查看最终成功率

## 性能优化建议

### 已实现的优化

✅ 线程独立会话
✅ 登录串行化（使用锁）
✅ 随机延迟（1-5秒启动延迟）
✅ 请求间隔（0.2-0.5秒）
✅ 指数退避重试（最多5次）
✅ 批量保存（1000条/批）

### 可调优配置

根据实际情况调整：

```bash
# 线程数（最重要）
STOCK_DAILY_MAX_WORKERS=2  # 建议值

# 批量保存大小
STOCK_BATCH_SIZE=1000  # 可以增加到 2000

# 日志级别（调试时使用）
LOG_LEVEL=DEBUG  # 生产环境用 INFO
```

## 备份建议

定期备份数据库和日志：

```bash
# 备份日志
tar -czf logs-backup-$(date +%Y%m%d).tar.gz logs/

# 数据库备份（根据实际数据库配置）
# 示例：docker compose exec db mysqldump ...
```

## 更多信息

- 详细优化说明：[docs/baostock_optimization.md](./baostock_optimization.md)
- 多线程说明：[docs/stock_daily_multithread.md](./stock_daily_multithread.md)

## 总结

**关键要点**：
1. ✅ 使用 2-3 个线程（不要超过 3）
2. ✅ 首次全量同步使用 1 个线程
3. ✅ 网络错误是正常的，已有重试机制
4. ✅ 关注最终成功率，而不是中间错误

**推荐配置**：
```bash
STOCK_DAILY_MAX_WORKERS=2
LOG_LEVEL=INFO
```

祝部署顺利！🚀
