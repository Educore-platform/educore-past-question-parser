"""
Matrix/pmatrix option detector.

Migrated from ``_try_format_as_matrix`` in ``latex_text.py``.  This resolver
is registered in the maths and physics option chains so that matrix-layout
options are detected and their LaTeX representation stored on the question dict
before the main LaTeX enricher runs.

The option resolver chain is called per-question inside
``QuestionExtractorHandler`` when a subject has ``"matrix"`` in its
``special_question_types``.
"""

from __future__ import annotations

import re
from typing import Optional

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

_NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")


def try_format_as_matrix(s: str) -> Optional[str]:
    """
    Detect a scalar × matrix pattern in *s* and return a LaTeX representation,
    or ``None`` if *s* does not look like matrix content.
    """
    lines = [ln.strip() for ln in s.strip().split("\n") if ln.strip()]

    if lines and re.match(r"^[A-Da-d][.)]\s*$", lines[0]):
        lines = lines[1:]

    if len(lines) < 2:
        return None

    scalar_latex: Optional[str] = None
    if re.match(r"^\d+(/\d+)?$", lines[0]):
        raw_scalar = lines[0]
        lines = lines[1:]
        if "/" in raw_scalar:
            a, b = raw_scalar.split("/", 1)
            scalar_latex = rf"\frac{{{a}}}{{{b}}}"
        else:
            scalar_latex = raw_scalar

    if len(lines) < 2:
        return None

    lines = [re.sub(r"^[\[\(]+|[\]\)]+$", "", ln).strip() for ln in lines]
    lines = [ln for ln in lines if ln]

    if len(lines) < 2:
        return None

    rows: list[list[str]] = []
    n_cols: Optional[int] = None
    for ln in lines:
        tokens = ln.split()
        if not tokens or not all(_NUM_RE.match(t) for t in tokens):
            return None
        if n_cols is None:
            n_cols = len(tokens)
        elif len(tokens) != n_cols:
            return None
        rows.append(tokens)

    if n_cols is None or n_cols < 2 or len(rows) < 2:
        return None

    body = r"\\".join(" & ".join(row) for row in rows)
    matrix_tex = r"\begin{pmatrix}" + body + r"\end{pmatrix}"
    inner = (scalar_latex + matrix_tex) if scalar_latex else matrix_tex
    return r"\(" + inner + r"\)"


class MatrixOptionStrategy(BaseResolverStrategy[dict]):
    """
    Detects matrix-layout options and returns a ``{letter: latex_string}`` dict
    where each value is the LaTeX representation of the matrix.

    Declines when no option in the block looks like a matrix.
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
            raw_val = opt_m.group(2).strip()
            matrix_latex = try_format_as_matrix(raw_val)
            if matrix_latex:
                options[letter] = matrix_latex

        return options if options else None
