import logging
import sys
from datetime import datetime


class LocalTimeFormatter(logging.Formatter):
    """使用本地时区的日志格式化器"""

    def formatTime(self, record, datefmt=None):
        """重写 formatTime 方法，使用本地时间而不是 UTC"""
        dt = datetime.fromtimestamp(record.created)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')


def setup_logger():
    """配置日志系统"""
    # 创建处理器
    handler = logging.StreamHandler(sys.stdout)

    # 使用本地时区的格式化器
    formatter = LocalTimeFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    return logging.getLogger(__name__)


logger = setup_logger()