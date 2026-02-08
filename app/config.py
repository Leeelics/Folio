from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""

    # Database
    database_url: str

    # OKX API
    okx_api_key: str = ""
    okx_secret_key: str = ""
    okx_passphrase: str = ""

    # OpenAI
    openai_api_key: str

    # Wedding Budget
    wedding_budget: float = 300000.0
    wedding_date: str = "2026-06-30"

    # Risk Management
    risk_margin_threshold: float = 0.2

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
