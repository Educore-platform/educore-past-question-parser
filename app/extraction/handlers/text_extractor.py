"""
Text extractor pipeline handler.

Iterates over every page in the open ``fitz.Document`` and extracts text
using ``extract_page_text_smart`` (column-aware reconstruction).

Always runs — every subject needs text.

Input:  ``doc`` (fitz.Document)
Output: ``TextExtractionOutput`` with a ``pages`` list of ``{page, text}`` dicts.
"""

from __future__ import annotations

from typing import Any

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import TextExtractionOutput
from app.extraction.resolvers.options.two_column_grid import extract_page_text_smart


class TextExtractorHandler:
    """Produce ``TextExtractionOutput`` from an open PDF document."""

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(self, doc: Any) -> TextExtractionOutput:
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = extract_page_text_smart(page)
            pages.append({"page": page_num + 1, "text": text.strip()})
        return TextExtractionOutput(pages=pages)
