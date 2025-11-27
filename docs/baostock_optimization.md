# Baostock 多线程优化与稳定性改进

## 问题背景

Baostock 服务器在多线程并发访问时频繁出现网络接收错误：
- `'utf-8' codec can't decode byte 0xXX`
- `Error -3 while decompressing data: invalid distance too far back`
- `接收数据异常，请稍后再试`

## 根本原因

1. **Baostock 服务器限制**：服务器无法承受高并发请求
2. **连接非线程安全**：共享连接在多线程环境下会冲突
3. **网络传输不稳定**：数据压缩/解压缩过程中易出错

## 优化措施

### 1. 线程独立会话 + 登录锁
```python
# 使用锁确保同一时间只有一个线程在登录
with self.login_lock:
    lg = bs.login()
    if lg.error_code == '0':
        time.sleep(0.5)  # 登录成功后短暂延迟

try:
    # 处理股票数据
    ...
finally:
    bs.logout()
```

**关键改进**：
- 使用 `Lock` 确保登录串行化，避免并发登录
- 登录成功后延迟 0.5 秒，给服务器缓冲时间
- 登录失败自动重试 3 次

### 2. 随机启动延迟
```python
# 避免所有线程同时启动 (1-5秒随机延迟)
time.sleep(random.uniform(1, 5))
```

### 3. 请求间隔控制
```python
# 每次查询后延迟 (0.2-0.5秒随机延迟)
time.sleep(random.uniform(0.2, 0.5))
```

### 4. 指数退避重试
```python
max_retries = 5  # 最多重试5次
base_retry_delay = 2  # 基础延迟2秒

for attempt in range(max_retries):
    try:
        # 请求 Baostock
        ...
    except Exception as e:
        # 每次重试延迟递增: 2秒, 4秒, 6秒, 8秒, 10秒
        retry_delay = base_retry_delay * (attempt + 1)
        time.sleep(retry_delay)
```

### 5. 保守的并发配置
```bash
# 推荐配置
STOCK_DAILY_MAX_WORKERS=2  # 2-3个线程

# 不推荐
STOCK_DAILY_MAX_WORKERS=5  # 会导致大量错误
```

## 配置建议

### 稳定性优先
```bash
STOCK_DAILY_MAX_WORKERS=1  # 串行处理，无并发错误
```
- **优点**：完全稳定，无网络错误
- **缺点**：速度最慢
- **适用**：首次全量同步，数据完整性要求高

### 平衡配置（推荐）
```bash
STOCK_DAILY_MAX_WORKERS=2  # 2-3个线程
```
- **优点**：稳定性好，速度提升明显
- **缺点**：偶尔会有少量错误（但有重试机制）
- **适用**：日常增量同步

### 激进配置（不推荐）
```bash
STOCK_DAILY_MAX_WORKERS=5  # 5个以上线程
```
- **优点**：速度最快
- **缺点**：大量网络错误，成功率低
- **适用**：不推荐使用

## 性能对比

假设同步 5000 只股票：

| 配置 | 线程数 | 预计耗时 | 错误率 | 推荐度 |
|------|--------|----------|--------|--------|
| 串行 | 1 | ~4小时 | 0% | ⭐⭐⭐ |
| 保守 | 2 | ~2小时 | <5% | ⭐⭐⭐⭐⭐ |
| 平衡 | 3 | ~1.5小时 | ~10% | ⭐⭐⭐⭐ |
| 激进 | 5 | ~1小时 | >30% | ⭐ |

## 错误处理策略

### 自动重试
- 网络错误自动重试 5 次
- 指数退避延迟 (2, 4, 6, 8, 10 秒)
- 重试失败后记录错误日志

### 失败股票处理
```python
# 单个股票失败不影响其他股票
if saved:
    success_count += 1
else:
    fail_count += 1
    # 记录失败股票，后续可手动重试
```

### 监控和日志
```python
# 每10只股票输出进度
if processed_count % 10 == 0:
    logger.info(
        f"进度: {processed_count}/{total} | "
        f"成功: {success_count} | 失败: {fail_count}"
    )
```

## 最佳实践

### 1. 首次全量同步
```bash
# 使用串行模式确保完整性
STOCK_DAILY_MAX_WORKERS=1
```

### 2. 日常增量同步
```bash
# 使用2-3线程平衡速度和稳定性
STOCK_DAILY_MAX_WORKERS=2
```

### 3. 失败重试
```bash
# 查看日志找出失败的股票
grep "✗" logs/app.log

# 针对失败股票单独重试
# 修改代码临时只处理失败的股票列表
```

### 4. 监控和调优
```bash
# 实时监控日志
tail -f logs/app.log | grep "进度"

# 根据错误率调整线程数
# 如果错误率 > 10%，减少线程数
# 如果错误率 < 1%，可以尝试增加线程数
```

## 代码位置

所有优化都在 `app/tasks/stock_daily_fetcher.py`:

- **线程处理**: 第 388-485 行 (`_process_single_stock`)
- **重试机制**: 第 547-635 行 (`_fetch_stock_daily_from_baostock_sync`)
- **延迟控制**: 第 409, 462 行
- **并发配置**: 第 44 行 (`self.max_workers`)

## 总结

通过以上优化措施，我们在保持多线程性能优势的同时，显著提升了系统稳定性：

✅ 线程独立会话 - 避免连接冲突
✅ 随机延迟 - 分散请求压力
✅ 指数退避重试 - 提高成功率
✅ 保守并发配置 - 平衡速度与稳定性

**推荐配置**: `STOCK_DAILY_MAX_WORKERS=2`，在稳定性和性能之间取得最佳平衡。
