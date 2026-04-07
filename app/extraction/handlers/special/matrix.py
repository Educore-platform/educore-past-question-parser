"""
Matrix question post-processor.

Matrix detection and LaTeX rendering are handled inside ``plain_to_latex_mixed``
in ``latex_text.py`` (called by ``LatexEnricherHandler``).  This handler is a
stub reserved for cases where a post-LaTeX matrix pass is needed.

Input:  ``questions`` list.
Output: ``QuestionExtractionOutput`` (passthrough — no-op stub).

Gated by ``"matrix" in profile.special_question_types``.
"""

from __future__ import annotations

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import QuestionExtractionOutput


class MatrixQuestionHandler:
    """
    Post-processing stub for matrix/table questions.

    Input:  ``questions`` list.
    Output: ``QuestionExtractionOutput`` (passthrough).

    Currently a no-op: matrix detection already runs inside ``LatexEnricherHandler``
    via ``_try_format_as_matrix`` in ``latex_text.py``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return "matrix" in profile.special_question_types

    def process(self, questions: list[dict]) -> QuestionExtractionOutput:
        return QuestionExtractionOutput(questions=questions)
