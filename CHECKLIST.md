# 提交前检查清单

## ✅ 快速检查

在提交代码到 GitHub 前，请运行以下命令：

```bash
# 1. 查看当前状态
git status

# 2. 确认没有敏感文件
git status | grep -E "\.env$|__pycache__|\.DS_Store|\.idea|\.egg-info"

# 3. 查看将要提交的修改
git diff --staged

# 4. 测试代码运行
python -m app.main
```

---

## 📋 详细检查清单

### 🔒 敏感文件检查

- [ ] 确认 `.env` 文件**未被追踪**
- [ ] 确认 `.env.example` **不包含真实密码**
- [ ] 确认没有 API 密钥或 token
- [ ] 确认没有数据库密码

### 🗑️ 不必要文件检查

- [ ] 确认 `__pycache__/` 目录**未被追踪**
- [ ] 确认 `.DS_Store` 文件**未被追踪**
- [ ] 确认 `.idea/` 目录**未被追踪**
- [ ] 确认 `*.pyc` 文件**未被追踪**
- [ ] 确认 `*.egg-info/` 目录**未被追踪**
- [ ] 确认 `logs/` 目录**未被追踪**
- [ ] 确认 `*.pid` 文件**未被追踪**

### 📦 依赖检查

- [ ] `pyproject.toml` 中的依赖都是必要的
- [ ] 没有遗留的 FastAPI/数据库依赖
- [ ] Python 版本要求正确 (>=3.8)

### 📄 文档检查

- [ ] `README.md` 内容准确、完整
- [ ] `.env.example` 包含所有必要的配置项
- [ ] 所有新增的文档都已添加

### 🧪 功能检查

- [ ] 代码可以正常导入
```bash
python -c "from app.core.config import settings; print('OK')"
```

- [ ] 日志模块正常
```bash
python -c "from app.utils.logger import logger; logger.info('Test')"
```

- [ ] 主服务可以导入
```bash
python -c "from app.main import TradingService; print('OK')"
```

---

## 🚀 提交建议的命令

### 查看将要提交的内容
```bash
git status
git diff --staged --name-only
```

### 如果发现问题，移除不该提交的文件
```bash
# 从暂存区移除文件（但保留本地文件）
git reset HEAD <file>

# 从 git 缓存中完全移除（保留本地文件）
git rm --cached <file>
```

### 确认无误后提交
```bash
git add .
git commit -m "优化项目结构，移除不必要的代码和依赖"
git push origin main
```

---

## ⚠️ 常见错误

### 1. 误提交了 .env 文件

**立即处理：**
```bash
# 从 git 中移除
git rm --cached .env

# 提交这个删除操作
git commit -m "移除 .env 文件"

# 推送
git push

# 重要：如果包含敏感信息，需要重置所有密钥！
```

### 2. 误提交了 __pycache__

```bash
# 从 git 中移除
git rm -r --cached __pycache__

# 提交
git commit -m "移除 __pycache__ 目录"
```

### 3. .gitignore 没有生效

```bash
# 清除所有缓存
git rm -r --cached .

# 重新添加
git add .

# 提交
git commit -m "刷新 .gitignore 规则"
```

---

## 📊 提交统计参考

一次完整的项目优化提交应该包含大约：

```
Changes to be committed:
  - 新文件：约 10-15 个 (文档、配置等)
  - 修改文件：约 5-10 个 (README, config 等)
  - 删除文件：约 80-100 个 (空文件、缓存等)
```

---

## 🎯 快速验证脚本

创建一个验证脚本 `check.sh`：

```bash
#!/bin/bash

echo "🔍 检查提交前状态..."

# 检查敏感文件
echo "检查敏感文件..."
git status | grep -E "\.env$" && echo "❌ 发现 .env 文件！" || echo "✅ .env 未被追踪"

# 检查缓存文件
echo "检查缓存文件..."
git status | grep "__pycache__" && echo "❌ 发现 __pycache__！" || echo "✅ __pycache__ 未被追踪"

# 检查系统文件
echo "检查系统文件..."
git status | grep "\.DS_Store" && echo "❌ 发现 .DS_Store！" || echo "✅ .DS_Store 未被追踪"

# 测试代码
echo "测试代码导入..."
python -c "from app.core.config import settings" && echo "✅ 配置模块正常" || echo "❌ 配置模块错误"
python -c "from app.utils.logger import logger" && echo "✅ 日志模块正常" || echo "❌ 日志模块错误"
python -c "from app.main import TradingService" && echo "✅ 主服务模块正常" || echo "❌ 主服务模块错误"

echo "✅ 检查完成！"
```

使用方法：
```bash
chmod +x check.sh
./check.sh
```

---

## 📚 相关文档

- [GIT_GUIDELINES.md](GIT_GUIDELINES.md) - 完整的 Git 使用指南
- [COMMIT_SUMMARY.md](COMMIT_SUMMARY.md) - 本次提交的详细总结
- [DEPENDENCY_CHECK.md](DEPENDENCY_CHECK.md) - 依赖分析

---

**最后提醒：提交前务必检查，推送后难以撤销！**
