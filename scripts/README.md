
# 禁用 zsh通配符扩展用于 pip安装

```bash
# 禁用 zsh 的通配符扩展用于 pip 安装
alias pip='noglob pip'
```
重新加载配置:
```bash
source ~/.zshrc
```
# 安装开发环境：

```bash
pip install -e .[dev]
# 或者
python scripts/install.py dev
```

# 安装生产环境 

```bash
pip install -e .[prod]
# 或者
python scripts/install.py prod
```

# 仅安装基础依赖

```bash
pip install -e .[prod]
# 或者
python scripts/install.py prod
```

# 运行

```bash
python -m app.main
```