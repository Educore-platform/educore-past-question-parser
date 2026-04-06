"""Single-column option parser: A.\\nB.\\nC.\\nD. format."""

from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

_OPT_LABEL_ONLY_RE = re.compile(r"^[A-Da-d][.)]\s*$")


class SingleColumnStrategy(BaseResolverStrategy[dict]):
    """
    Fallback option parser for straightforward single-column layouts.

    Identical regex to ``TwoColumnGridStrategy`` but runs only when the grid
    strategy has already declined or failed for the current question block.
    In practice, this handles PDFs where ``extract_page_text_smart`` already
    linearised two-column content, so the two strategies are complementary
    rather than competing.
    """

    def extract(self, ctx: ExtractionContext) -> dict | None:
        raw = ctx._active_q_text
        if not raw:
            return None

        first_opt = re.search(r"\n([A-Da-d])[.)]\s*\S", raw)
        if not first_opt:
            return None

        options_raw = "\n" + raw[first_opt.start():]
        options: dict[str, str] = {}
        for opt_m in re.finditer(
            r"\n([A-Da-d])[.)]\s*(.*?)(?=\n[A-Da-d][.)]|\Z)",
            options_raw,
            re.DOTALL,
        ):
            letter = opt_m.group(1).upper()
            raw_lines = opt_m.group(2).strip().split("\n")
            val = "\n".join(" ".join(ln.split()) for ln in raw_lines if ln.strip())
            if val:
                options[letter] = val

        if not options or all(_OPT_LABEL_ONLY_RE.match(v) for v in options.values()):
            return None

        return options if len(options) >= 2 else None
