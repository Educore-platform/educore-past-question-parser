import re
import uuid
from pathlib import Path
from typing import Optional

from fastapi import UploadFile

from app.core.config import settings


def _sanitize_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]", "_", base, flags=re.UNICODE)
    return base or "document.pdf"


class FileService:
    """Persists uploaded PDFs under the project data directory."""

    def __init__(self, upload_dir: Optional[Path] = None) -> None:
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def resolve_stored_path(self, stored_name: str) -> Path:
        path = (self.upload_dir / stored_name).resolve()
        if not str(path).startswith(str(self.upload_dir.resolve())):
            raise ValueError("Invalid path")
        return path

    def save_pdf_bytes(self, original_filename: str, content: bytes) -> dict:
        """Write validated PDF bytes to disk (same metadata shape as ``save_pdf``)."""
        if not original_filename or not original_filename.lower().endswith(".pdf"):
            raise ValueError("A PDF file (.pdf) is required")
        if not content:
            raise ValueError("Empty file")

        safe = _sanitize_filename(original_filename)
        stored_name = f"{uuid.uuid4().hex[:12]}_{safe}"
        dest = self.upload_dir / stored_name
        dest.write_bytes(content)

        rel = dest.relative_to(settings.PROJECT_ROOT)
        return {
            "stored_filename": stored_name,
            "original_filename": original_filename,
            "absolute_path": str(dest),
            "relative_path": str(rel).replace("\\", "/"),
            "size_bytes": len(content),
        }

    async def save_pdf(self, file: UploadFile) -> dict:
        """
        Save an uploaded PDF to disk. Returns metadata including the stored filename
        (unique prefix + sanitized original name).
        """
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise ValueError("A PDF file (.pdf) is required")
        content = await file.read()
        return self.save_pdf_bytes(file.filename, content)


_file_service: Optional[FileService] = None


def get_file_service() -> FileService:
    global _file_service
    if _file_service is None:
        _file_service = FileService()
    return _file_service
