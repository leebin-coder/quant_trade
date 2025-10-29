## 健康检查路由
from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.database.connection import get_db_session

router = APIRouter(tags=["系统健康检查"])


@router.get("/health")
async def health_check():
    """基础健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Quant Trade System",
        "version": "1.0.0"
    }


@router.get("/health/db")
async def database_health_check(session: AsyncSession = Depends(get_db_session)):
    """数据库健康检查"""
    try:
        # 测试数据库连接
        result = await session.execute("SELECT 1")
        db_status = "connected" if result.scalar() == 1 else "disconnected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": db_status,
        "service": "Quant Trade System"
    }


@router.get("/health/full")
async def full_health_check(session: AsyncSession = Depends(get_db_session)):
    """完整健康检查"""
    health_info = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {}
    }

    # 检查数据库
    try:
        result = await session.execute("SELECT 1")
        health_info["services"]["database"] = {
            "status": "healthy",
            "message": "Database connection successful"
        }
    except Exception as e:
        health_info["status"] = "degraded"
        health_info["services"]["database"] = {
            "status": "unhealthy",
            "message": str(e)
        }

    # 检查其他服务（后续添加）
    health_info["services"]["api"] = {
        "status": "healthy",
        "message": "API service running"
    }

    return health_info