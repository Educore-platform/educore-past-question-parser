"""
Logarithm / antilog table question handler — stub.

Some maths papers include questions where a log or antilog table is embedded
in the question or answer options.  This handler is reserved for detecting and
formatting those.

Gated by ``"logarithm" in profile.special_question_types``.
"""

from __future__ import annotations

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile


class LogarithmHandler:
    """Not yet implemented — always runs (can_handle returns True) but is a no-op."""

    def can_handle(self, profile: CapabilityProfile) -> bool:
        return "logarithm" in profile.special_question_types

    def process(self, ctx: ExtractionContext) -> ExtractionContext:
        return ctx
