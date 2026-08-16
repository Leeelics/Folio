"""API 认证模块"""
import os
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# 从环境变量获取 API 密钥
API_KEY = os.getenv("API_KEY", "folio-dev-key-2026")  # 开发环境默认值

security = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """验证 API 密钥

    用法：
        @router.get("/protected", dependencies=[Depends(verify_api_key)])
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


def get_cors_origins() -> list[str]:
    """获取允许的 CORS 来源

    开发环境允许 localhost，生产环境应该配置具体域名
    """
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        # 生产环境从环境变量读取
        origins_str = os.getenv("ALLOWED_ORIGINS", "")
        if origins_str:
            return [o.strip() for o in origins_str.split(",")]
        # 如果没有配置，使用默认域名
        return ["https://folio.example.com"]

    # 开发环境
    return [
        "http://localhost:8501",  # Streamlit 开发服务器
        "http://127.0.0.1:8501",
        "http://localhost:8000",  # 后端 API
        "http://127.0.0.1:8000",
    ]
