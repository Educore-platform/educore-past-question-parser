"""
Answer-key pipeline handler.

Preprocesses the full extracted text (noise stripping, year-banner normalisation)
and splits it into per-year ``(year, question_text, answer_dict)`` sections using
the ``AnswerKeyResolverChain``.

Always runs — every subject may have an answer section.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.profiles.chains import ANSWER_CHAINS


class AnswerKeyHandler:
    """
    Populate ``ctx.year_sections`` and ``ctx.answer_key`` from the extracted pages.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        chain = ANSWER_CHAINS.get(ctx.subject.lower(), ANSWER_CHAINS["__default__"])
        result = chain.resolve(ctx)

        if result.value:
            ctx.year_sections = result.value
        else:
            # Fallback: no parseable answer block — treat the entire text as one section
            from app.extraction.resolvers.answers.answers_block import (
                normalise_year_banners,
                strip_noise,
            )
            import re

            raw = "\n".join(strip_noise(p["text"]) for p in ctx.pages)
            clean = re.sub(r"\n__YR__\d+\n", "\n", normalise_year_banners(raw))
            ctx.year_sections = [(None, clean, {})]

        # Build flat answer_key map for convenience
        for year, _q_text, answers in ctx.year_sections:
            for q_num, letter in answers.items():
                ctx.answer_key[(year, q_num)] = letter

        return ctx
