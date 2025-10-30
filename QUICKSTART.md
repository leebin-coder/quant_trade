# 快速启动指南

## 1. 环境准备

确保已安装 Python 3.8+：

```bash
python --version
```

## 2. 安装依赖

```bash
# 安装项目依赖
pip install -e .

# 或者使用开发依赖
pip install -e ".[dev]"
```

## 3. 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，根据需要修改配置：

```bash
# 交易配置
TRADING_ENABLED=false       # 是否启用真实交易
SIMULATION_MODE=true        # 模拟模式

# 数据源
DATA_PROVIDER=akshare       # 数据提供者：akshare 或 yfinance

# 日志级别
LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR

# 调度间隔（秒）
MARKET_MONITOR_INTERVAL=60         # 市场监控间隔
STRATEGY_EXECUTION_INTERVAL=300    # 策略执行间隔
HEALTH_CHECK_INTERVAL=30           # 健康检查间隔
```

## 4. 启动服务

### 方式 1: 使用服务管理脚本（推荐）

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

### 方式 2: 直接运行

```bash
# 前台运行（可以看到实时输出）
python -m app.main

# 或者
python app/main.py

# 后台运行
nohup python -m app.main > logs/service.log 2>&1 &
```

### 方式 3: 使用 Docker

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

## 5. 验证服务运行

检查日志文件：

```bash
tail -f logs/service.log
```

你应该看到类似的输出：

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

## 6. 常用操作

### 查看进程

```bash
ps aux | grep "app.main"
```

### 查看 PID 文件

```bash
cat quant_trade.pid
```

### 清理日志

```bash
rm -rf logs/*.log
```

### 重新加载配置

修改 `.env` 文件后，需要重启服务：

```bash
python scripts/service_manager.py restart
```

## 7. 开机自启动

### macOS (launchd)

```bash
# 复制 plist 文件
cp deployment/com.quanttrade.service.plist ~/Library/LaunchAgents/

# 加载服务
launchctl load ~/Library/LaunchAgents/com.quanttrade.service.plist

# 启动服务
launchctl start com.quanttrade.service
```

### Linux (systemd)

```bash
# 复制服务文件
sudo cp deployment/quant-trade.service /etc/systemd/system/

# 重载 systemd
sudo systemctl daemon-reload

# 启用开机自启动
sudo systemctl enable quant-trade

# 启动服务
sudo systemctl start quant-trade

# 查看状态
sudo systemctl status quant-trade
```

### 使用 Supervisor

```bash
# 安装 supervisor
pip install supervisor

# 复制配置
sudo cp deployment/supervisor.conf /etc/supervisor/conf.d/quant-trade.conf

# 重载配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl start quant-trade
```

## 8. 故障排除

### 服务无法启动

1. 检查 Python 路径：
```bash
which python3
```

2. 检查依赖安装：
```bash
pip list | grep pandas
```

3. 查看详细错误：
```bash
python -m app.main
```

### 找不到模块错误

确保在项目根目录运行：

```bash
cd /Users/libin/Projects/quant_trade
python -m app.main
```

### 权限错误

添加执行权限：

```bash
chmod +x scripts/service_manager.py
chmod +x app/main.py
```

### 端口被占用

检查是否有其他实例在运行：

```bash
ps aux | grep "app.main"
pkill -f "app.main"
```

## 9. 下一步

- 阅读 [deployment/README.md](deployment/README.md) 了解详细部署选项
- 查看 [README.md](README.md) 了解项目架构
- 开始开发你的交易策略

## 10. 获取帮助

如有问题，请查看：

- 日志文件：`logs/service.log`
- 项目文档：`docs/`
- GitHub Issues
