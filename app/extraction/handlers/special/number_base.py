"""
Number-base notation post-processor stub.

Number-base conversion (``6r78`` → ``\\(6r7_{8}\\)``) runs inside
``plain_to_latex_mixed`` in ``latex_text.py`` (called by ``LatexEnricherHandler``).
This handler is reserved for future post-LaTeX detection passes.

Gated by ``"number_base" in profile.special_question_types``.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile


class NumberBaseHandler:
    """
    Post-processing stub for number-base notation questions.

    Currently a no-op: conversion already runs inside ``LatexEnricherHandler``.
    """

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return "number_base" in profile.special_question_types

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        return ctx
