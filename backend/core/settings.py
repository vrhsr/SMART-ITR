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

    database_url: str = "postgresql+psycopg://user:pass@localhost:5432/smartitr"
    aws_region: str = "ap-south-1"
    jwt_secret: str = "change-me-in-prod"
    razorpay_key_id: str = "rzp_test_key"
    razorpay_key_secret: str = "rzp_test_secret"
    razorpay_webhook_secret: str = "change-me-webhook"


settings = Settings()

