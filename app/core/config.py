import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application configuration (paths resolved from project root)."""

    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "educore")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # environment: production | development
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    _raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001")
    ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

    PAPER_CODE_BATCH_SIZE: int = 5
    PAPER_CODE_REFILL_THRESHOLD: float = 0.25

    CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY", "")
    CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET", "")
    CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


settings = Settings()
