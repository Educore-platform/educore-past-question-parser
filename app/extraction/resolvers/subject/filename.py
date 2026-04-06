from __future__ import annotations

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext
from app.extraction.resolvers.subject.first_page_keyword import KNOWN_SUBJECTS


class FileNameStrategy(BaseResolverStrategy[str]):
    """Infer subject from the PDF filename (e.g. ``biology_2010.pdf``)."""

    def extract(self, ctx: ExtractionContext) -> str | None:
        stem = ctx.pdf_path.stem.lower()
        for subj in KNOWN_SUBJECTS:
            if subj.lower() in stem:
                return subj.title()
        return None
