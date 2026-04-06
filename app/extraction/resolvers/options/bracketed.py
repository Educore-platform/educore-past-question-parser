"""Stub: (A)(B)(C)(D) bracketed option format."""

from __future__ import annotations

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext


class BracketedStrategy(BaseResolverStrategy[dict]):
    """Not yet implemented — always declines."""

    def can_handle(self, ctx: ExtractionContext) -> bool:  # noqa: ARG002
        return False

    def extract(self, ctx: ExtractionContext) -> dict | None:  # noqa: ARG002
        return None
