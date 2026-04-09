import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application configuration (paths resolved from project root)."""

    PROJECT_ROOT: Path = _project_root()
    UPLOAD_DIR: Path = PROJECT_ROOT / "data" / "uploads"
    IMAGES_DIR: Path = PROJECT_ROOT / "data" / "images"

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "educore")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # Comma-separated list of allowed CORS origins.
    # Defaults cover local development; override via ALLOWED_ORIGINS in production.
    ALLOWED_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "ALLOWED_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if o.strip()
    ]

    PAPER_CODE_BATCH_SIZE: int = 5
    PAPER_CODE_REFILL_THRESHOLD: float = 0.25


settings = Settings()
