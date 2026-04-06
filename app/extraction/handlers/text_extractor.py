"""
Text extractor pipeline handler.

Iterates over every page in the open ``fitz.Document`` stored on the context
and extracts text using ``extract_page_text_smart`` (column-aware reconstruction
from ``resolvers/options/two_column_grid.py``).

Always runs — every subject needs text.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.resolvers.options.two_column_grid import extract_page_text_smart


class TextExtractorHandler:
    """Populate ``ctx.pages`` from ``ctx.doc``."""

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        pages = []
        for page_num in range(len(ctx.doc)):
            page = ctx.doc[page_num]
            text = extract_page_text_smart(page)
            pages.append({"page": page_num + 1, "text": text.strip()})
        ctx.pages = pages
        return ctx
