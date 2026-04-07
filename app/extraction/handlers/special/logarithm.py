"""
Logarithm / antilog table question handler — stub.

Some maths papers include questions where a log or antilog table is embedded
in the question or answer options.  This handler is reserved for detecting and
formatting those.

Input:  ``questions`` list.
Output: ``QuestionExtractionOutput`` (passthrough — no-op stub).

Gated by ``"logarithm" in profile.special_question_types``.
"""

from __future__ import annotations

from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import QuestionExtractionOutput


class LogarithmHandler:
    """
    Stub handler for logarithm/antilog table questions.

    Input:  ``questions`` list.
    Output: ``QuestionExtractionOutput`` (passthrough).

    Not yet implemented.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return "logarithm" in profile.special_question_types

    def process(self, questions: list[dict]) -> QuestionExtractionOutput:
        return QuestionExtractionOutput(questions=questions)
