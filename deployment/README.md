# 服务部署说明

## 快速启动（推荐）

使用项目提供的服务管理脚本：

```bash
# 启动服务
python scripts/service_manager.py start

# 停止服务
python scripts/service_manager.py stop

# 重启服务
python scripts/service_manager.py restart

# 查看状态
python scripts/service_manager.py status

# 查看日志
python scripts/service_manager.py logs
```

## 直接运行

```bash
# 前台运行
python -m app.main

# 或者
python app/main.py

# 后台运行
nohup python -m app.main > logs/service.log 2>&1 &
```

## 使用 systemd (Linux)

1. 编辑服务文件，修改路径和用户名：
```bash
nano deployment/quant-trade.service
```

2. 复制服务文件：
```bash
sudo cp deployment/quant-trade.service /etc/systemd/system/
```

3. 重载 systemd：
```bash
sudo systemctl daemon-reload
```

4. 启用服务（开机自启动）：
```bash
sudo systemctl enable quant-trade
```

5. 启动服务：
```bash
sudo systemctl start quant-trade
```

6. 查看状态：
```bash
sudo systemctl status quant-trade
```

7. 查看日志：
```bash
sudo journalctl -u quant-trade -f
```

## 使用 Supervisor

1. 安装 supervisor：
```bash
pip install supervisor
# 或
sudo apt-get install supervisor
```

2. 复制配置文件：
```bash
sudo cp deployment/supervisor.conf /etc/supervisor/conf.d/quant-trade.conf
```

3. 重载配置：
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

4. 管理服务：
```bash
# 启动
sudo supervisorctl start quant-trade

# 停止
sudo supervisorctl stop quant-trade

# 重启
sudo supervisorctl restart quant-trade

# 查看状态
sudo supervisorctl status quant-trade
```

## 使用 launchd (macOS)

1. 创建 plist 文件：
```bash
cp deployment/com.quanttrade.service.plist ~/Library/LaunchAgents/
```

2. 加载服务：
```bash
launchctl load ~/Library/LaunchAgents/com.quanttrade.service.plist
```

3. 启动服务：
```bash
launchctl start com.quanttrade.service
```

4. 查看状态：
```bash
launchctl list | grep quanttrade
```

## 使用 Docker

```bash
# 构建镜像
docker build -t quant-trade .

# 运行容器
docker run -d \
  --name quant-trade \
  --restart unless-stopped \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/logs:/app/logs \
  quant-trade
```

## 环境变量配置

在 `.env` 文件中配置：

```bash
# 项目信息
PROJECT_NAME="Quant Trade"
VERSION="1.0.0"

# 交易配置
TRADING_ENABLED=false
SIMULATION_MODE=true

# 数据源
DATA_PROVIDER=akshare

# 日志级别
LOG_LEVEL=INFO

# 调度间隔（秒）
MARKET_MONITOR_INTERVAL=60
STRATEGY_EXECUTION_INTERVAL=300
HEALTH_CHECK_INTERVAL=30
```

## 监控和日志

- 服务日志：`logs/service.log`
- PID 文件：`quant_trade.pid`
- 使用 `tail -f logs/service.log` 实时查看日志

## 故障排除

### 服务无法启动
1. 检查 Python 环境是否正确
2. 检查 `.env` 文件是否存在
3. 查看日志文件获取详细错误信息

### 服务意外停止
1. 检查系统资源（内存、CPU）
2. 查看日志文件中的错误信息
3. 确认所需的依赖都已安装

### 权限问题
```bash
# 给脚本添加执行权限
chmod +x scripts/service_manager.py
chmod +x app/main.py
```
