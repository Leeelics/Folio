import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.investment_routes import router as investment_router
from app.api.routes import router
from app.api.stock_routes import router as stock_router
from app.api.brokerage_routes import router as brokerage_router
from app.api.core_routes import router as core_router
from app.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting Equilibra Financial Management System...")
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Equilibra...")


# Create FastAPI application
app = FastAPI(
    title="Equilibra - Personal Financial Management System",
    description="个人财务管理系统后端 API - 集成 OKX、A/H 股、AI 分析",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="/api/v1", tags=["Financial Management"])
app.include_router(stock_router, prefix="/api/v1", tags=["Stock Market"])
app.include_router(investment_router, prefix="/api/v1", tags=["Investment Management"])
app.include_router(brokerage_router, prefix="/api/v1", tags=["Brokerage Accounts"])
app.include_router(core_router, prefix="/api/v1", tags=["Core Phase 1"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Equilibra Financial Management System",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "equilibra-api"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
