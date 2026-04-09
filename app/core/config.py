import os
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


class Settings:
    """Application configuration (paths resolved from project root)."""

    PROJECT_ROOT: Path = _project_root()
    UPLOAD_DIR: Path = PROJECT_ROOT / "data" / "uploads"
    IMAGES_DIR: Path = PROJECT_ROOT / "data" / "images"

    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DB_NAME: str = os.getenv("DB_NAME", "educore")

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # environment: production | development
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Comma-separated list of allowed CORS origins.
    # Defaults cover local development; override via ALLOWED_ORIGINS in production.
    @property
    def ALLOWED_ORIGINS(self) -> list[str]:
        raw = os.getenv("ALLOWED_ORIGINS", "")
        if not raw:
            return ["http://localhost:3000", "http://127.0.0.1:3000"]
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    PAPER_CODE_BATCH_SIZE: int = 5
    PAPER_CODE_REFILL_THRESHOLD: float = 0.25


settings = Settings()
