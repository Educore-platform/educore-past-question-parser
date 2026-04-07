"""
Vector OCR repairer — stub for future general maths vector repair.

Input:  ``questions`` list.
Output: ``QuestionExtractionOutput`` (unchanged passthrough).

Gated by ``profile.has_ocr_vectors``.  When implemented, this handler would
repair rendered-vector maths symbols (arrows, overlines, etc.) that the PDF
text layer omits entirely, using a high-DPI Tesseract pass.

Currently a no-op: dental-formula OCR repair (the only existing OCR repair
in the codebase) is handled by ``DentalFormulaHandler`` in ``handlers/special/``.
"""

from __future__ import annotations

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import QuestionExtractionOutput


class VectorOCRRepairerHandler:
    """
    Pipeline handler for general vector-OCR repair.

    Input:  ``questions`` list.
    Output: ``QuestionExtractionOutput`` (passthrough — no-op stub).

    Gated by ``profile.has_ocr_vectors``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return profile.has_ocr_vectors

    def process(self, questions: list[dict]) -> QuestionExtractionOutput:
        return QuestionExtractionOutput(questions=questions)
