from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="",
        extra="ignore"
    )

    # App
    debug: bool = False
    environment: str = "development"
    
    # Database
    database_url: str = "postgresql+psycopg://user:pass@localhost:5432/smartitr"
    
    # AWS
    aws_region: str = "ap-south-1"
    s3_bucket: str = "smartitr-docs"
    
    # Auth
    jwt_secret: str = "change-me-in-prod"
    
    # Billing
    razorpay_key_id: str = "rzp_test_key"
    razorpay_key_secret: str = "rzp_test_secret"
    razorpay_webhook_secret: str = "change-me-webhook"
    
    # CORS
    cors_origins: list[str] = ["*"]


settings = Settings()

