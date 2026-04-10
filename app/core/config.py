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

    ALLOWED_ORIGINS: list[str] = os.getenv("ALLOWED_ORIGINS", "").split(",")

    PAPER_CODE_BATCH_SIZE: int = 5
    PAPER_CODE_REFILL_THRESHOLD: float = 0.25

    CLOUDINARY_URL: str = os.getenv("CLOUDINARY_URL", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def IMAGES_DIR(self) -> Path:
        p = _project_root() / "data" / "images"
        p.mkdir(parents=True, exist_ok=True)
        return p

settings = Settings()
