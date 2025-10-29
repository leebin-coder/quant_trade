from fastapi import FastAPI
from app.core.config import settings
from app.utils.logger import logger

# 导入API路由
from app.api.routes.health import router as health_router
from app.api.routes.data import router as data_router
from app.api.routes.strategies import router as strategies_router
from app.api.routes.trading import router as trading_router
from app.api.routes.portfolio import router as portfolio_router
from app.api.routes.system import router as system_router

# 创建FastAPI应用
app = FastAPI(
    title=settings.project_name,
    description="专业的量化交易和自动交易系统",
    version=settings.version,
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# 注册API路由
app.include_router(health_router, prefix="/api/health", tags=["系统健康检查"])
app.include_router(data_router, prefix="/api/data", tags=["数据管理"])
app.include_router(strategies_router, prefix="/api/strategies", tags=["策略管理"])
app.include_router(trading_router, prefix="/api/trading", tags=["交易执行"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["组合管理"])
app.include_router(system_router, prefix="/api/system", tags=["系统管理"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用 Quant Trade 量化交易系统",
        "status": "running",
        "version": settings.version,
        "docs": "/docs",
        "health_check": "/api/health/health",
        "available_endpoints": {
            "数据管理": "/api/data",
            "策略管理": "/api/strategies",
            "交易执行": "/api/trading",
            "组合管理": "/api/portfolio",
            "系统管理": "/api/system",
            "健康检查": "/api/health/health"
        }
    }


@app.get("/info")
async def system_info():
    """系统信息"""
    return {
        "name": settings.project_name,
        "version": settings.version,
        "description": "基于 FastAPI 和 AsyncSQLAlchemy 的专业量化交易系统",
        "database": {
            "host": settings.db_host,
            "port": settings.db_port,
            "name": settings.db_name
        },
        "api": {
            "host": settings.api_host,
            "port": settings.api_port
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info(f"🚀 启动 {settings.project_name} v{settings.version}")
    logger.info(f"📊 数据库: {settings.db_host}:{settings.db_port}/{settings.db_name}")
    logger.info(f"🌐 API服务: http://{settings.api_host}:{settings.api_port}")

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level="info"
    )