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