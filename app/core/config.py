# app/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """应用配置设置"""

    # 项目基本信息
    project_name: str = Field("Quant Trade", env="PROJECT_NAME")
    version: str = Field("1.0.0", env="VERSION")

    # API 服务器配置
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")
    api_reload: bool = Field(True, env="API_RELOAD")

    # 交易配置
    trading_enabled: bool = Field(False, env="TRADING_ENABLED")
    simulation_mode: bool = Field(True, env="SIMULATION_MODE")

    # 数据库配置 (扁平结构)
    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_user: str = Field(..., env="DB_USER")
    db_password: str = Field(..., env="DB_PASSWORD")
    db_name: str = Field("quant_trade", env="DB_NAME")

    # 日志配置
    log_level: str = Field("INFO", env="LOG_LEVEL")

    @property
    def database_url(self) -> str:
        """构建数据库连接URL"""
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    class Config:
        env_file = ".env"
        case_sensitive = False


# 创建全局配置实例
settings = Settings()