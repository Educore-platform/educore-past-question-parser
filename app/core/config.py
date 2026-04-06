import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application configuration (paths resolved from project root)."""

    PROJECT_ROOT: Path = _project_root()
    UPLOAD_DIR: Path = PROJECT_ROOT / "data" / "uploads"
    IMAGES_DIR: Path = PROJECT_ROOT / "data" / "images"

    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "educore")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    PAPER_CODE_BATCH_SIZE: int = 5
    PAPER_CODE_REFILL_THRESHOLD: float = 0.25


settings = Settings()
