# app/infrastructure/database/connection.py
## 数据库连接（异步）
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy异步基类"""
    pass


class DatabaseManager:
    """异步数据库管理器"""

    def __init__(self):
        # 使用新的配置方式
        db_url = settings.database_url

        self.engine = create_async_engine(
            db_url,
            echo=True,  # 开发时显示SQL日志
            future=True
        )

        self.async_session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def get_session(self) -> AsyncSession:
        """获取异步数据库会话"""
        async with self.async_session_factory() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"数据库会话错误: {e}")
                raise
            finally:
                await session.close()


# 全局数据库管理器
db_manager = DatabaseManager()


# 依赖注入使用的会话获取器
async def get_db_session() -> AsyncSession:
    """获取数据库会话的依赖项"""
    async for session in db_manager.get_session():
        yield session