# Git 提交指南

## 应该提交到 GitHub 的文件

### ✅ 源代码
```
app/
├── __init__.py
├── main.py
├── core/
│   ├── __init__.py
│   └── config.py
└── utils/
    ├── __init__.py
    └── logger.py
```

### ✅ 配置文件
```
pyproject.toml              # 项目配置和依赖
.env.example                # 环境变量模板（不含敏感信息）
.gitignore                  # Git 忽略规则
.dockerignore               # Docker 忽略规则
```

### ✅ 部署文件
```
deployment/
├── README.md
├── quant-trade.service      # systemd 配置
├── supervisor.conf          # Supervisor 配置
└── com.quanttrade.service.plist  # launchd 配置

Dockerfile                   # Docker 镜像配置
docker-compose.yml           # Docker Compose 配置
```

### ✅ 脚本文件
```
scripts/
├── service_manager.py      # 服务管理脚本
└── README.md
```

### ✅ 文档文件
```
README.md                   # 项目说明
QUICKSTART.md              # 快速启动指南
PROJECT_STRUCTURE.md       # 项目结构说明
GIT_GUIDELINES.md          # 本文件
LICENSE                    # 许可证（如果有）
```

### ✅ 测试文件
```
tests/                     # 测试代码
```

---

## ❌ 不应该提交到 GitHub 的文件

### ❌ Python 生成文件
```
__pycache__/              # Python 字节码缓存
*.pyc, *.pyo, *.pyd       # 编译的 Python 文件
*.egg-info/               # 安装包信息
dist/, build/             # 构建输出
```

### ❌ 虚拟环境
```
venv/
env/
.venv/
ENV/
```

### ❌ IDE 配置
```
.vscode/                  # VS Code 配置
.idea/                    # PyCharm/IntelliJ 配置
*.swp, *.swo              # Vim 临时文件
.DS_Store                 # macOS 系统文件
```

### ❌ 敏感信息
```
.env                      # 环境变量（包含敏感信息）
*.key                     # 密钥文件
*.pem                     # 证书文件
secrets/                  # 密钥目录
credentials.json          # 凭证文件
```

### ❌ 运行时文件
```
logs/                     # 日志文件
*.log
*.pid                     # 进程 ID 文件
quant_trade.pid           # 服务进程文件
```

### ❌ 数据文件
```
storage/                  # 存储目录
data/                     # 数据目录
*.db, *.sqlite            # 数据库文件
*.csv, *.xlsx             # 数据文件
```

### ❌ 测试和覆盖率
```
.pytest_cache/            # Pytest 缓存
.coverage                 # 覆盖率数据
htmlcov/                  # 覆盖率报告
.tox/                     # Tox 测试环境
```

### ❌ 临时文件
```
*.tmp, *.temp             # 临时文件
*.bak                     # 备份文件
*~                        # 编辑器临时文件
```

---

## 📝 Git 工作流程

### 1. 检查当前状态
```bash
git status
```

### 2. 添加文件到暂存区
```bash
# 添加所有修改的文件
git add .

# 或者选择性添加
git add app/
git add README.md
git add pyproject.toml
```

### 3. 查看将要提交的内容
```bash
# 查看暂存的修改
git diff --staged

# 查看简短状态
git status --short
```

### 4. 提交更改
```bash
git commit -m "描述你的更改"

# 示例
git commit -m "优化项目结构，移除不必要的空文件"
git commit -m "添加服务管理脚本"
git commit -m "更新文档"
```

### 5. 推送到远程仓库
```bash
git push origin main
```

---

## 🛠️ 清理已提交的不该提交的文件

如果已经误提交了不该提交的文件，使用以下命令清理：

### 清理单个文件
```bash
git rm --cached .env
git rm --cached .DS_Store
```

### 清理目录
```bash
git rm -r --cached __pycache__
git rm -r --cached .idea
git rm -r --cached quant_trade.egg-info
git rm -r --cached logs
```

### 然后提交删除操作
```bash
git commit -m "移除不该提交的文件"
git push
```

---

## 🔍 检查 .gitignore 是否生效

### 测试 .gitignore
```bash
# 查看哪些文件被忽略
git status --ignored

# 检查特定文件是否被忽略
git check-ignore -v .env
git check-ignore -v __pycache__
```

### 强制刷新 .gitignore
```bash
# 移除所有文件的缓存
git rm -r --cached .

# 重新添加所有文件
git add .

# 提交
git commit -m "刷新 .gitignore 规则"
```

---

## 📋 提交前检查清单

在每次提交前，请确认：

- [ ] 没有提交 `.env` 文件
- [ ] 没有提交 `__pycache__` 目录
- [ ] 没有提交 `.DS_Store` 等系统文件
- [ ] 没有提交 IDE 配置（`.idea`, `.vscode`）
- [ ] 没有提交日志文件
- [ ] 没有提交数据库文件
- [ ] 没有提交临时文件
- [ ] `.env.example` 不包含真实密码
- [ ] 提交信息清晰明确

---

## 💡 最佳实践

1. **频繁提交**：小步快跑，每个功能点都提交
2. **清晰的提交信息**：使用动词开头，简明扼要
3. **提交前审查**：使用 `git diff` 检查修改
4. **分支开发**：重要功能在独立分支开发
5. **定期推送**：避免本地积累太多未推送的提交

---

## 🚨 紧急情况处理

### 撤销最后一次提交（未推送）
```bash
git reset --soft HEAD~1
```

### 修改最后一次提交信息（未推送）
```bash
git commit --amend -m "新的提交信息"
```

### 撤销已推送的提交
```bash
# 慎用！会改写历史
git revert HEAD
git push
```

### 误提交了敏感信息
1. 立即从仓库中删除
2. 重置所有受影响的密码/密钥
3. 考虑使用 `git filter-branch` 或 BFG 清理历史

---

## 📚 相关资源

- [Git 官方文档](https://git-scm.com/doc)
- [GitHub .gitignore 模板](https://github.com/github/gitignore)
- [语义化提交信息](https://www.conventionalcommits.org/)
