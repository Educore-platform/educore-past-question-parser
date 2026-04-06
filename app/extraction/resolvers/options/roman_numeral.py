"""Stub: (i)(ii)(iii)(iv) roman-numeral option format used by some publishers."""

from __future__ import annotations

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext


class RomanNumeralOptionStrategy(BaseResolverStrategy[dict]):
    """
    Not yet implemented — always declines.

    Plug into a subject or source chain via::

        chain.plug(RomanNumeralOptionStrategy(), at=0)
    """

    def can_handle(self, ctx: ExtractionContext) -> bool:  # noqa: ARG002
        return False

    def extract(self, ctx: ExtractionContext) -> dict | None:  # noqa: ARG002
        return None
