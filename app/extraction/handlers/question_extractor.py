"""
Question extractor pipeline handler.

For each ``(year, q_text, answers)`` section produced by ``AnswerKeyHandler``,
this handler invokes the subject-specific ``QuestionResolverChain`` to parse
individual questions.

Always runs — every subject needs question extraction.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.profiles.chains import QUESTION_CHAINS


class QuestionExtractorHandler:
    """Populate ``ctx.questions`` by iterating over ``ctx.year_sections``."""

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        chain = QUESTION_CHAINS.get(ctx.subject.lower(), QUESTION_CHAINS["__default__"])

        all_questions: list[dict] = []
        for year, q_text, answers in ctx.year_sections:
            # Stage temporary state that resolver strategies read from ctx
            ctx._active_q_text = q_text
            ctx._active_year = year
            ctx._active_answers = answers

            result = chain.resolve(ctx)
            if result.value:
                all_questions.extend(result.value)

        # Clear temporary state
        ctx._active_q_text = ""
        ctx._active_year = None
        ctx._active_answers = {}

        ctx.questions = all_questions
        return ctx
