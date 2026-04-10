import re
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import cloudinary
import cloudinary.uploader

from fastapi import UploadFile

from app.core.config import settings


def _sanitize_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\-]", "_", base, flags=re.UNICODE)
    return base or "document.pdf"


class FileService(ABC):
    """Abstract interface for PDF storage services."""

    @abstractmethod
    def save_pdf_bytes(self, original_filename: str, content: bytes, public_id: Optional[str] = None) -> dict:
        """
        Persists PDF bytes and returns metadata.
        Expected keys in dict: original_filename, size_bytes, file_url, cloudinary_public_id (optional)
        """
        pass

    @abstractmethod
    def save_image_bytes(self, filename: str, content: bytes, public_id: Optional[str] = None) -> dict:
        """
        Persists image bytes and returns metadata.
        Expected keys in dict: file_url, cloudinary_public_id (optional)
        """
        pass

    async def save_pdf(self, file: UploadFile) -> dict:
        """Helper to read UploadFile and call save_pdf_bytes."""
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise ValueError("A PDF file (.pdf) is required")
        content = await file.read()
        return self.save_pdf_bytes(file.filename, content)


class CloudinaryFileService(FileService):
    """Persists uploaded PDFs to Cloudinary."""

    def __init__(self) -> None:
       if not settings.CLOUDINARY_API_KEY or not settings.CLOUDINARY_API_SECRET or not settings.CLOUDINARY_CLOUD_NAME:
           raise ValueError("CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, and CLOUDINARY_CLOUD_NAME are required")
       cloudinary.config(
           cloud_name=settings.CLOUDINARY_CLOUD_NAME,
           api_key=settings.CLOUDINARY_API_KEY,
           api_secret=settings.CLOUDINARY_API_SECRET,
       )

    def save_pdf_bytes(self, original_filename: str, content: bytes, public_id: Optional[str] = None) -> dict:
        if not original_filename or not original_filename.lower().endswith(".pdf"):
            raise ValueError("A PDF file (.pdf) is required")
        if not content:
            raise ValueError("Empty file")

        # Use the folder 'educore/uploads' by default
        # If public_id is provided, Cloudinary uses it exactly.
        upload_result = cloudinary.uploader.upload(
            content,
            resource_type="raw",
            folder="educore/uploads",
            public_id=public_id or f"{uuid.uuid4().hex[:8]}_{_sanitize_filename(original_filename)}",
        )

        return {
            "original_filename": original_filename,
            "file_url": upload_result.get("secure_url"),
            "cloudinary_public_id": upload_result.get("public_id"),
            "size_bytes": len(content),
        }

    def save_image_bytes(self, filename: str, content: bytes, public_id: Optional[str] = None) -> dict:
        if not content:
            raise ValueError("Empty file")

        # Use the folder 'educore/images' for extracted question diagrams
        upload_result = cloudinary.uploader.upload(
            content,
            resource_type="image",
            folder="educore/images",
            public_id=public_id or Path(filename).stem,
        )

        return {
            "file_url": upload_result.get("secure_url"),
            "cloudinary_public_id": upload_result.get("public_id"),
        }


_file_service: Optional[FileService] = None


def get_file_service() -> FileService:
    global _file_service
    if _file_service is None:
        _file_service = CloudinaryFileService()
    return _file_service
