"""
Detect subject from ``Subject YYYY`` style section headers.

Some JAMB PDFs (e.g. compiled multi-year Mathematics papers) use inline
year-section headers of the form ``Mathematics 1983``, ``Biology 1990`` etc.
rather than the standard ``1983 JAMB MATHEMATICS QUESTIONS`` banner.

This strategy scans all pages for a line that matches one of the known subjects
followed by a 4-digit year, and returns the subject name.
"""

from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext
from app.extraction.resolvers.subject.first_page_keyword import KNOWN_SUBJECTS

_subjects_pattern = "|".join(re.escape(s) for s in KNOWN_SUBJECTS)
_SUBJ_YR_RE = re.compile(
    rf"^({_subjects_pattern})\s+\d{{4}}\s*$",
    re.MULTILINE | re.IGNORECASE,
)


class SubjectYearBannerStrategy(BaseResolverStrategy[str]):
    """
    Scans all pages for a ``<Subject> <YYYY>`` header line (e.g. ``Mathematics 1983``)
    and returns the matched subject name.

    Reads ``ctx.doc`` directly so it can run before ``ctx.pages`` is populated.
    """

    def extract(self, ctx: ExtractionContext) -> str | None:
        all_text = "\n".join(ctx.doc[i].get_text() for i in range(len(ctx.doc)))
        m = _SUBJ_YR_RE.search(all_text)
        if m:
            return m.group(1).strip().title()
        return None
