"""
Answer-key pipeline handler.

Preprocesses the full extracted text (noise stripping, year-banner normalisation)
and splits it into per-year ``(year, question_text, answer_dict)`` sections using
the ``AnswerKeyResolverChain``.

Always runs — every subject may have an answer section.

Input:  ``pages`` list of ``{page, text}`` dicts, ``subject`` string,
        ``pdf_path`` (for context construction only).
Output: ``AnswerKeyOutput`` with ``year_sections`` and flat ``answer_key`` map.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.core.stages import AnswerKeyOutput
from app.extraction.profiles.chains import ANSWER_CHAINS


class AnswerKeyHandler:
    """
    Produce ``AnswerKeyOutput`` (``year_sections`` + ``answer_key``) from extracted pages.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:  # noqa: ARG002
        return True

    def process(self, pages: list[dict], subject: str, pdf_path: Path) -> AnswerKeyOutput:
        # Build a local resolver context carrying only the fields the
        # AnswerKey resolver strategies access.
        _ctx = ExtractionContext(pdf_path=pdf_path, doc=None, subject=subject)
        _ctx.pages = pages

        chain = ANSWER_CHAINS.get(subject.lower(), ANSWER_CHAINS["__default__"])
        result = chain.resolve(_ctx)

        if result.value:
            year_sections = result.value
        else:
            # Fallback: no parseable answer block — treat the entire text as one section.
            from app.extraction.resolvers.answers.answers_block import (
                normalise_year_banners,
                strip_noise,
            )

            raw = "\n".join(strip_noise(p["text"]) for p in pages)
            clean = re.sub(r"\n__YR__\d+\n", "\n", normalise_year_banners(raw))
            year_sections = [(None, clean, {})]

        # Build flat answer_key convenience map.
        answer_key: dict[tuple, str] = {}
        for year, _q_text, answers in year_sections:
            for q_num, letter in answers.items():
                answer_key[(year, q_num)] = letter

        return AnswerKeyOutput(year_sections=year_sections, answer_key=answer_key)
