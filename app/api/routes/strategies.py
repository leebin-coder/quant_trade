# 策略管理API路由
from fastapi import APIRouter

router = APIRouter(tags=["策略管理"])

@router.get("/")
async def get_strategies():
    """策略管理根路径"""
    return {"message": "策略管理模块 - 开发中"}

@router.get("/list")
async def list_strategies():
    """获取策略列表"""
    return {"message": "策略列表 - 开发中"}