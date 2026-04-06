from __future__ import annotations

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext


class ManualOverrideStrategy(BaseResolverStrategy[str]):
    """Returns the subject override passed in via the API, if provided."""

    def can_handle(self, ctx: ExtractionContext) -> bool:
        return bool(ctx.subject_override)

    def extract(self, ctx: ExtractionContext) -> str | None:
        return ctx.subject_override or None
