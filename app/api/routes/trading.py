# 交易执行API路由
from fastapi import APIRouter

router = APIRouter(tags=["交易执行"])

@router.get("/")
async def get_trading():
    """交易执行根路径"""
    return {"message": "交易执行模块 - 开发中"}

@router.get("/status")
async def get_trading_status():
    """获取交易状态"""
    return {"message": "交易状态 - 开发中"}