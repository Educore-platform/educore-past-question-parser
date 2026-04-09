"""
Detect subject from year-section banners embedded in the PDF text.

JAMB PDFs contain lines such as "2010 JAMB BIOLOGY QUESTIONS" and
"2015 JAMB FURTHER MATHEMATICS QUESTIONS" which reliably identify the subject.
"""

from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext
from app.extraction.resolvers.subject.first_page_keyword import KNOWN_SUBJECTS

_BANNER_RE = re.compile(
    r"(?:UTME|JAMB)\s+(\d{4})\s+([A-Z]+(?:\s+[A-Z]+)?)\s+QUESTIONS|"
    r"(\d{4})\s+(?:UTME|JAMB)\s+([A-Z]+(?:\s+[A-Z]+)?)\s+QUESTIONS",
    re.IGNORECASE,
)

_KNOWN_UPPER = {s.upper() for s in KNOWN_SUBJECTS}


class TitleBannerStrategy(BaseResolverStrategy[str]):
    """
    Scans all pages for a JAMB year-section banner and extracts the subject word(s).

    Reads ``ctx.doc`` directly so it can run before ``ctx.pages`` is populated.

    The captured word is validated against ``KNOWN_SUBJECTS`` to prevent false
    positives such as matching "Past" from cover-page text like
    "1983-2004 / JAMB / Past / Questions".
    """

    def extract(self, ctx: ExtractionContext) -> str | None:
        all_text = " ".join(ctx.doc[i].get_text() for i in range(len(ctx.doc)))
        m = _BANNER_RE.search(all_text)
        if m:
            # Group 2 (UTME YYYY SUBJ) or Group 4 (YYYY UTME SUBJ)
            subj_raw = m.group(2) or m.group(4)
            if not subj_raw:
                return None
            candidate = subj_raw.strip().title()
            if candidate.upper() in _KNOWN_UPPER:
                return candidate
        return None
