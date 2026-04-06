"""
Detect subject by scanning the first page for known subject keywords.

Longer/more-specific subjects come first to avoid substring matches
(e.g. "Further Mathematics" must be checked before "Mathematics").
"""

from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

# Ordered: longer/more-specific phrases before their substrings.
KNOWN_SUBJECTS: list[str] = [
    "FURTHER MATHEMATICS",
    "COMPUTER SCIENCE",
    "ENGLISH LANGUAGE",
    "BIOLOGY",
    "CHEMISTRY",
    "PHYSICS",
    "MATHEMATICS",
    "ENGLISH",
    "GOVERNMENT",
    "ECONOMICS",
    "GEOGRAPHY",
    "LITERATURE",
    "HISTORY",
    "ACCOUNTING",
    "COMMERCE",
    "AGRICULTURE",
    "CRS",
    "IRS",
]


class FirstPageKeywordStrategy(BaseResolverStrategy[str]):
    """
    Reads the first PDF page directly from ``ctx.doc`` and searches for known
    subject keywords.  Case-insensitive whole-word match.
    """

    def can_handle(self, ctx: ExtractionContext) -> bool:
        return len(ctx.doc) > 0

    def extract(self, ctx: ExtractionContext) -> str | None:
        text_upper = ctx.doc[0].get_text().upper()
        for subj in KNOWN_SUBJECTS:
            if re.search(r"\b" + subj + r"\b", text_upper):
                return subj.title()
        return None
