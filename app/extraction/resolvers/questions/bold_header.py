"""Stub: bold question-number headers (non-JAMB PDF sources)."""

from __future__ import annotations

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext


class BoldHeaderStrategy(BaseResolverStrategy[list]):
    """Not yet implemented — always declines."""

    def can_handle(self, ctx: ExtractionContext) -> bool:  # noqa: ARG002
        return False

    def extract(self, ctx: ExtractionContext) -> list | None:  # noqa: ARG002
        return None
