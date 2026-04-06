"""
LaTeX enrichment handler.

Wraps ``build_latex_for_question`` and ``options_latex_for_persist`` from the
existing ``latex_text.py`` utility module.  Gated by ``profile.has_formulas``.

Adds ``question_latex`` and ``options_latex`` fields to every question dict.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.services.latex_text import build_latex_for_question, options_latex_for_persist


def attach_latex_fields(questions: list[dict]) -> None:
    """In-place: populate ``question_latex`` / ``options_latex`` on each question."""
    for q in questions:
        ql, om = build_latex_for_question(q["question"], q["options"])
        q["question_latex"] = ql
        q["options_latex"] = options_latex_for_persist(om)


class LatexEnricherHandler:
    """
    Pipeline handler that attaches LaTeX representations to every parsed question.

    Gated by ``profile.has_formulas``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return profile.has_formulas

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        attach_latex_fields(ctx.questions)
        return ctx
