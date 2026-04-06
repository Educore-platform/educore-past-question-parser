"""Uniform JSON envelope for every API response."""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    error: Optional[Any] = Field(
        default=None,
        description="Structured error payload when success is false; null on success",
    )
    data: Optional[T] = Field(default=None, description="Response payload when success is true")
    message: str = Field(default="", description="Human-readable summary")


def api_success(data: Optional[T] = None, message: str = "") -> ApiResponse[T]:
    return ApiResponse(success=True, error=None, data=data, message=message)
