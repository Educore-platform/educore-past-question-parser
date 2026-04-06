"""
Vector OCR repairer — stub for future general maths vector repair.

Gated by ``profile.has_ocr_vectors``.  When implemented, this handler would
repair rendered-vector maths symbols (arrows, overlines, etc.) that the PDF
text layer omits entirely, using a high-DPI Tesseract pass.

Currently a no-op: dental-formula OCR repair (the only existing OCR repair
in the codebase) is handled by ``DentalFormulaHandler`` in ``handlers/special/``.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile


class VectorOCRRepairerHandler:
    """
    Pipeline handler for general vector-OCR repair.

    Gated by ``profile.has_ocr_vectors``.  Currently a no-op stub.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return profile.has_ocr_vectors

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        # No-op until a general vector-OCR repair strategy is implemented.
        return ctx
