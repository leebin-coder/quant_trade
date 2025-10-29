# 系统管理API路由
from fastapi import APIRouter

router = APIRouter(tags=["系统管理"])

@router.get("/")
async def get_system():
    """系统管理根路径"""
    return {"message": "系统管理模块 - 开发中"}

@router.get("/config")
async def get_system_config():
    """获取系统配置"""
    return {"message": "系统配置 - 开发中"}