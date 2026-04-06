"""Run with: uvicorn app.main:app --reload (preferred) or: uvicorn main:app --reload"""

from app.main import app

__all__ = ["app"]
