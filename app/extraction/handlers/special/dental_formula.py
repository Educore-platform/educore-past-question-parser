"""
Dental-formula Tesseract OCR repair handler.

Migrated from ``repair_vector_fraction_options`` in ``pdf_math_ocr.py``.

JAMB Biology dental-formula questions draw stacked fractions as vector art;
the PDF text layer only contains tooth labels (I, C, pm, m) with no digits.
This handler renders the option band at high DPI and runs Tesseract to recover
the fractions.

Input:  ``questions`` list, ``pdf_path``.
Output: ``QuestionExtractionOutput`` with repaired option text.

Gated by ``"dental_formula" in profile.special_question_types``.
"""

from __future__ import annotations

from pathlib import Path

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import QuestionExtractionOutput
from app.services.pdf_math_ocr import repair_vector_fraction_options


class DentalFormulaHandler:
    """
    Pipeline handler that OCR-repairs missing fractions in dental-formula questions.

    Input:  ``questions`` list, ``pdf_path``.
    Output: ``QuestionExtractionOutput`` (repaired in-place).

    Gated by ``"dental_formula" in profile.special_question_types``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return "dental_formula" in profile.special_question_types

    def process(self, questions: list[dict], pdf_path: Path) -> QuestionExtractionOutput:
        repair_vector_fraction_options(questions, str(pdf_path))
        return QuestionExtractionOutput(questions=questions)
