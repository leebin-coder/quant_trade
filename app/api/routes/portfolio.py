# 组合管理API路由
from fastapi import APIRouter

router = APIRouter(tags=["组合管理"])

@router.get("/")
async def get_portfolio():
    """组合管理根路径"""
    return {"message": "组合管理模块 - 开发中"}

@router.get("/list")
async def list_portfolios():
    """获取组合列表"""
    return {"message": "组合列表 - 开发中"}