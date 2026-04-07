"""
Question extractor pipeline handler.

For each ``(year, q_text, answers)`` section produced by ``AnswerKeyHandler``,
invokes the subject-specific ``QuestionResolverChain`` to parse individual
questions.

Always runs — every subject needs question extraction.

Input:  ``year_sections``, ``image_map``, ``subject``, ``pdf_path``.
Output: ``QuestionExtractionOutput`` with the parsed ``questions`` list.
"""

from __future__ import annotations

from pathlib import Path

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import QuestionExtractionOutput
from app.extraction.profiles.chains import QUESTION_CHAINS


class QuestionExtractorHandler:
    """Produce ``QuestionExtractionOutput`` by iterating over ``year_sections``."""

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(
        self,
        year_sections: list,
        image_map: dict,
        subject: str,
        pdf_path: Path,
    ) -> QuestionExtractionOutput:
        # Build a local resolver context.  The _active_* fields are set per
        # section just before each chain.resolve() call — they are purely
        # internal to this handler and are never shared with other handlers.
        _ctx = ExtractionContext(pdf_path=pdf_path, doc=None, subject=subject)
        _ctx.image_map = image_map

        chain = QUESTION_CHAINS.get(subject.lower(), QUESTION_CHAINS["__default__"])

        all_questions: list[dict] = []
        for year, q_text, answers in year_sections:
            _ctx._active_q_text = q_text
            _ctx._active_year = year
            _ctx._active_answers = answers

            result = chain.resolve(_ctx)
            if result.value:
                all_questions.extend(result.value)

        # Clear staging so the context is clean if anything inspects it later.
        _ctx._active_q_text = ""
        _ctx._active_year = None
        _ctx._active_answers = {}

        return QuestionExtractionOutput(questions=all_questions)
