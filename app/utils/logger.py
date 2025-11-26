import logging
import sys
import time

# 关键：全局设置 logging.Formatter 使用本地时间
# 这会影响所有使用 logging 模块的库（包括 APScheduler）
logging.Formatter.converter = time.localtime


class LocalTimeFormatter(logging.Formatter):
    """使用本地时区的日志格式化器"""
    pass  # converter 已经在全局设置


def setup_logger():
    """配置日志系统"""
    # 清除所有现有的处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建处理器
    handler = logging.StreamHandler(sys.stdout)

    # 使用本地时区的格式化器
    formatter = LocalTimeFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # 配置根日志记录器
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    return logging.getLogger(__name__)


logger = setup_logger()