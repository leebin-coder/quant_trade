# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置设置"""

    # 项目基本信息
    project_name: str = Field("Quant Trade", env="PROJECT_NAME")
    version: str = Field("1.0.0", env="VERSION")

    # 交易配置
    trading_enabled: bool = Field(False, env="TRADING_ENABLED")
    simulation_mode: bool = Field(True, env="SIMULATION_MODE")

    # 数据源配置
    data_provider: str = Field("akshare", env="DATA_PROVIDER")  # akshare, yfinance

    # 股票API配置
    stock_api_host: str = Field("localhost", env="STOCK_API_HOST")
    stock_api_port: int = Field(8080, env="STOCK_API_PORT")
    stock_api_token: str = Field(
        "eyJhbGciOiJIUzUxMiJ9.eyJzZXJ2aWNlIjoicHl0aG9uLXNlcnZpY2UiLCJ0eXBlIjoic2VydmljZSIsInVzZXJJZCI6OTk5OTk5LCJpYXQiOjE3NjE5ODc3OTksImV4cCI6NDkxNTU4Nzc5OX0.Vh_apdQtxXXDkgC0uHmaRcYJ9D87LYALfZs9-fBAU6_48TsS8FoC4N-ZTK9JmUQ0BR4ltq8uDqGbZXYwLAE8RQ",
        env="STOCK_API_TOKEN"
    )
    stock_fetch_interval: int = Field(28800, env="STOCK_FETCH_INTERVAL")  # 8小时 = 28800秒（已废弃，使用 cron 调度）
    stock_batch_size: int = Field(1000, env="STOCK_BATCH_SIZE")  # 批量插入每批数量

    # 股票更新批次控制配置
    stock_update_batch_size: int = Field(100, env="STOCK_UPDATE_BATCH_SIZE")  # 每批更新数量
    stock_update_batch_pause: int = Field(300, env="STOCK_UPDATE_BATCH_PAUSE")  # 每批之间暂停秒数（5分钟=300秒）
    stock_update_item_delay: float = Field(0.2, env="STOCK_UPDATE_ITEM_DELAY")  # 每只股票之间的延迟秒数

    # 股票数据获取调度配置（每天凌晨0:00执行）
    stock_fetch_schedule_hour: int = Field(0, env="STOCK_FETCH_SCHEDULE_HOUR")  # 小时（24小时制）
    stock_fetch_schedule_minute: int = Field(0, env="STOCK_FETCH_SCHEDULE_MINUTE")  # 分钟
    stock_fetch_schedule_day_of_week: str = Field("*", env="STOCK_FETCH_SCHEDULE_DAY_OF_WEEK")  # 每天

    # 公司信息获取调度配置（每周末凌晨1:00执行）
    company_fetch_schedule_hour: int = Field(1, env="COMPANY_FETCH_SCHEDULE_HOUR")  # 小时（24小时制）
    company_fetch_schedule_minute: int = Field(0, env="COMPANY_FETCH_SCHEDULE_MINUTE")  # 分钟
    company_fetch_schedule_day_of_week: str = Field("sat,sun", env="COMPANY_FETCH_SCHEDULE_DAY_OF_WEEK")  # 周末

    # 交易日历获取调度配置（每天凌晨2:00执行）
    trading_calendar_schedule_hour: int = Field(2, env="TRADING_CALENDAR_SCHEDULE_HOUR")  # 小时（24小时制）
    trading_calendar_schedule_minute: int = Field(0, env="TRADING_CALENDAR_SCHEDULE_MINUTE")  # 分钟
    trading_calendar_schedule_day_of_week: str = Field("*", env="TRADING_CALENDAR_SCHEDULE_DAY_OF_WEEK")  # 每天

    # 日志配置
    log_level: str = Field("INFO", env="LOG_LEVEL")

    # 调度配置
    market_monitor_interval: int = Field(60, env="MARKET_MONITOR_INTERVAL")  # 秒
    strategy_execution_interval: int = Field(300, env="STRATEGY_EXECUTION_INTERVAL")  # 秒
    health_check_interval: int = Field(30, env="HEALTH_CHECK_INTERVAL")  # 秒

    class Config:
        env_file = ".env"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()