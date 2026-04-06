from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext
from app.extraction.resolvers.subject.first_page_keyword import KNOWN_SUBJECTS


class MetadataStrategy(BaseResolverStrategy[str]):
    """Scan PDF metadata fields (title, subject, keywords, …) for a subject keyword."""

    def extract(self, ctx: ExtractionContext) -> str | None:
        meta = ctx.doc.metadata or {}
        combined = " ".join(str(v) for v in meta.values() if v).upper()
        if not combined.strip():
            return None
        for subj in KNOWN_SUBJECTS:
            if re.search(r"\b" + subj + r"\b", combined):
                return subj.title()
        return None
