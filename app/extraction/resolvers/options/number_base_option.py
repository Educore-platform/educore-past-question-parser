"""
Number-base option detector.

Migrated from ``_format_base_notation`` / ``_BASE_WITH_VAR_RE`` / ``_BASE_PURE_RE``
in ``latex_text.py``.  Detects options that contain number-base notation
(e.g. ``6r78``, ``5119``) and returns them with inline LaTeX subscripts.
"""

from __future__ import annotations

import re

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

_BASE_WITH_VAR_RE = re.compile(
    r"\b(\d[0-9A-Za-z]*[a-zA-Z][0-9A-Za-z]*)(2|8|9|10|16)(?!\d)"
)
_BASE_CONTEXT_RE = re.compile(
    r"\b(base|binary|octal|hexadecimal|denary|number\s+system)\b",
    re.IGNORECASE,
)
_BASE_PURE_RE = re.compile(r"(?<!\d)(\d{2,})(2|8|9|10|16)(?!\d)")

_OPT_RE = re.compile(
    r"\n([A-Da-d])[.)]\s*(.*?)(?=\n[A-Da-d][.)]|\Z)",
    re.DOTALL,
)


def _apply_base_notation(text: str) -> str:
    in_base_context = bool(_BASE_CONTEXT_RE.search(text)) or bool(
        _BASE_WITH_VAR_RE.search(text)
    )

    def _sub(m: re.Match) -> str:
        return rf"\({m.group(1)}_{{{m.group(2)}}}\)"

    text = _BASE_WITH_VAR_RE.sub(_sub, text)
    if in_base_context:
        text = _BASE_PURE_RE.sub(_sub, text)
    return text


class NumberBaseOptionStrategy(BaseResolverStrategy[dict]):
    """
    Detects options containing number-base notation and returns them with
    LaTeX subscript formatting applied.  Declines when no base notation is found.
    """

    def extract(self, ctx: ExtractionContext) -> dict | None:
        raw = ctx._active_q_text
        if not raw:
            return None

        if not (_BASE_WITH_VAR_RE.search(raw) or _BASE_CONTEXT_RE.search(raw)):
            return None

        first_opt = re.search(r"\n([A-Da-d])[.)]\s*\S", raw)
        if not first_opt:
            return None

        options_raw = "\n" + raw[first_opt.start():]
        options: dict[str, str] = {}
        for opt_m in _OPT_RE.finditer(options_raw):
            letter = opt_m.group(1).upper()
            raw_lines = opt_m.group(2).strip().split("\n")
            val = "\n".join(" ".join(ln.split()) for ln in raw_lines if ln.strip())
            if val:
                options[letter] = _apply_base_notation(val)

        return options if len(options) >= 2 else None
