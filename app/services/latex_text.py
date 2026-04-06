"""
Convert plain text extracted from PDFs into LaTeX suitable for math-capable renderers.

Handles:
- Numeric fractions ``a/b`` (e.g. dental counts ``4/4``, ``2/3``) → ``\\(\\frac{a}{b}\\)``
- Unicode vulgar fractions (½, ⅓, ⅔, …) → ``\\frac{n}{d}``
- Common math symbols (×, ÷, °, ², ³, ≤, ≥, …)
- Number-base notation (e.g. ``6r78`` → ``\\(6r7_{8}\\)``, ``5119`` → ``\\(511_{9}\\)``)
- Literal text wrapped in ``\\text{...}`` with LaTeX special characters escaped

Output is intended for ``amsmath`` / ``unicode-math`` style documents or KaTeX/MathJax
when wrapped in a minimal preamble or rendered field-by-field.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# Unicode vulgar fractions → (numerator, denominator)
_UNICODE_FRAC: dict[str, tuple[int, int]] = {
    "½": (1, 2),
    "⅓": (1, 3),
    "⅔": (2, 3),
    "¼": (1, 4),
    "¾": (3, 4),
    "⅕": (1, 5),
    "⅙": (1, 6),
    "⅚": (5, 6),
    "⅛": (1, 8),
    "⅜": (3, 8),
    "⅝": (5, 8),
    "⅞": (7, 8),
}

# Single-character symbols → LaTeX (inline math fragments, no outer \(…\) here)
_SYM_TEX: list[tuple[str, str]] = [
    ("×", r"\times "),
    ("·", r"\cdot "),
    ("÷", r"\div "),
    ("≤", r"\leq "),
    ("≥", r"\geq "),
    ("≠", r"\neq "),
    ("±", r"\pm "),
    ("−", r"-"),  # unicode minus
    ("°", r"^{\circ}"),
    ("²", r"^2"),
    ("³", r"^3"),
    ("⁴", r"^4"),
]

# Match: numeric a/b | unicode fraction | single math symbol char
_TOKEN = re.compile(
    r"(\d{1,2}\s*/\s*\d{1,2})|([½⅓⅔¼¾⅕⅙⅚⅛⅜⅝⅞])|([×·÷≤≥≠±−°²³⁴])",
)

# ── Number-base notation detection ───────────────────────────────────────────
# PDFs lose subscript formatting, so "6r7₈" is extracted as "6r78" and
# "511₉" as "5119". We detect these by looking for a number token immediately
# followed (no space) by a valid base indicator (2, 8, 9, 10, 16).

# Unambiguous: the number part contains at least one letter variable (e.g. "6r78").
_BASE_WITH_VAR_RE = re.compile(
    r"\b(\d[0-9A-Za-z]*[a-zA-Z][0-9A-Za-z]*)(2|8|9|10|16)(?!\d)"
)

# Contextual keywords that confirm this is a number-base question.
_BASE_CONTEXT_RE = re.compile(
    r"\b(base|binary|octal|hexadecimal|denary|number\s+system)\b",
    re.IGNORECASE,
)

# Pure digit sequence + base indicator — only applied when context is confirmed.
_BASE_PURE_RE = re.compile(
    r"(?<!\d)(\d{2,})(2|8|9|10|16)(?!\d)"
)

# Split string at already-injected inline math boundaries so we don't double-process.
_INLINE_MATH_RE = re.compile(r"\\\(.*?\\\)")


def _escape_latex_text(s: str) -> str:
    """Escape characters that are special in LaTeX text mode."""
    return (
        s.replace("\\", r"\textbackslash{}")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("#", r"\#")
        .replace("$", r"\$")
        .replace("%", r"\%")
        .replace("&", r"\&")
        .replace("_", r"\_")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def _apply_symbol_replacements_in_literal(s: str) -> str:
    """Turn unicode math symbols inside a literal segment into inline math."""
    if not any(sym in s for sym, _ in _SYM_TEX):
        return r"\text{" + _escape_latex_text(s) + "}"
    pat = "|".join(re.escape(u) for u, _ in _SYM_TEX)
    chunks = re.split(f"({pat})", s)
    out: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        matched_tex = None
        for u, tex in _SYM_TEX:
            if chunk == u:
                matched_tex = tex.strip()
                break
        if matched_tex is not None:
            out.append(r"\(" + matched_tex + r"\)")
        else:
            out.append(r"\text{" + _escape_latex_text(chunk) + "}")
    return "".join(out)


def _try_format_as_matrix(s: str) -> Optional[str]:
    """
    Detect a scalar × matrix pattern in *s* and return a LaTeX representation,
    or ``None`` if *s* does not look like matrix content.

    Recognised input shapes (after the optional option-label prefix is stripped):

    * Single-line flat:  ``"1/5 2 1 3 4"``  (no row info — cannot detect)
    * Multi-line rows:   ``"1/5\\n2 1\\n3 4"``  →
                         ``\\(\\frac{1}{5}\\begin{pmatrix}2&1\\\\3&4\\end{pmatrix}\\)``
    * Rows with brackets: ``"1/5\\n[2 1]\\n[3 4]"``  → same output

    A matrix is detected when:
    - At least two rows remain after stripping the scalar and bracket-only lines.
    - Every row has the same number of tokens.
    - Every token is a (possibly negative) integer or simple decimal.
    - At least two columns are present.
    """
    lines = [ln.strip() for ln in s.strip().split("\n") if ln.strip()]

    # Strip leading option label ("A.", "B.", …)
    if lines and re.match(r"^[A-Da-d][.)]\s*$", lines[0]):
        lines = lines[1:]

    if len(lines) < 2:
        return None

    # Separate optional scalar prefix (single fraction or integer on its own line)
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

    # Strip surrounding bracket characters from every row
    lines = [re.sub(r"^[\[\(]+|[\]\)]+$", "", ln).strip() for ln in lines]
    lines = [ln for ln in lines if ln]  # drop bracket-only lines

    if len(lines) < 2:
        return None

    # Validate: every line must be the same number of numeric tokens
    _NUM_RE = re.compile(r"^-?\d+(\.\d+)?$")
    rows: List[List[str]] = []  
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

    # Build LaTeX
    body = r"\\".join(" & ".join(row) for row in rows)
    matrix_tex = r"\begin{pmatrix}" + body + r"\end{pmatrix}"
    inner = (scalar_latex + matrix_tex) if scalar_latex else matrix_tex
    return r"\(" + inner + r"\)"


def _format_base_notation(text: str) -> str:
    """
    Replace concatenated number-base notation with LaTeX subscript inline math.

    Two cases are handled:
    - Unambiguous: number with an embedded letter variable (e.g. "6r78" → \\(6r7_{8}\\)).
      These are always converted regardless of surrounding context.
    - Pure digits (e.g. "5119" → \\(511_{9}\\)): only converted when the text already
      contains a variable-style base number OR an explicit base keyword, to avoid
      false positives on regular numeric values.
    """
    in_base_context = bool(_BASE_CONTEXT_RE.search(text)) or bool(_BASE_WITH_VAR_RE.search(text))

    def _sub(m: re.Match) -> str:
        return rf"\({m.group(1)}_{{{m.group(2)}}}\)"

    text = _BASE_WITH_VAR_RE.sub(_sub, text)
    if in_base_context:
        text = _BASE_PURE_RE.sub(_sub, text)
    return text


def _process_plain_segment(s: str) -> str:
    """Apply fraction/symbol token processing to a plain (non-math) text segment."""
    if not s:
        return ""
    out: list[str] = []
    pos = 0
    for m in _TOKEN.finditer(s):
        if m.start() > pos:
            out.append(_apply_symbol_replacements_in_literal(s[pos:m.start()]))
        if m.group(1):
            a, b = re.split(r"\s*/\s*", m.group(1), maxsplit=1)
            out.append(r"\(\frac{" + a.strip() + "}{" + b.strip() + r"}\)")
        elif m.group(2):
            n, d = _UNICODE_FRAC[m.group(2)]
            out.append(r"\(\frac{" + str(n) + "}{" + str(d) + r"}\)")
        else:
            sym = m.group(3)
            for u, tex in _SYM_TEX:
                if u == sym:
                    out.append(r"\(" + tex.strip() + r"\)")
                    break
        pos = m.end()
    if pos < len(s):
        out.append(_apply_symbol_replacements_in_literal(s[pos:]))
    return "".join(out)


def plain_to_latex_mixed(s: str) -> str:
    """
    Turn *s* into a LaTeX fragment mixing ``\\text{…}`` and inline math ``\\(…\\)``.

    Examples
    --------
    ``pm 4/4, m 2/3`` → ``\\text{pm }\\(\\frac{4}{4}\\)\\text{, m }\\(\\frac{2}{3}\\)``
    ``m2⅓`` → ``\\text{m2}\\(\\frac{1}{3}\\)``
    ``6r78 = 5119`` → ``\\(6r7_{8}\\)\\text{ = }\\(511_{9}\\)``
    ``1/5\\n2 1\\n3 4`` → ``\\(\\frac{1}{5}\\begin{pmatrix}2&1\\\\3&4\\end{pmatrix}\\)``
    """
    if not s.strip():
        return ""

    # Matrix detection runs first, *before* whitespace normalisation, because
    # it relies on the newline row-structure preserved by the parser.
    matrix_latex = _try_format_as_matrix(s)
    if matrix_latex is not None:
        return matrix_latex

    s = " ".join(s.split())
    if not s:
        return ""

    # Pre-pass: detect number-base notation and inject inline math for it.
    # This must happen before the main token loop so the injected \(...\) does
    # not get escaped by _escape_latex_text.
    s = _format_base_notation(s)

    # Split at inline math boundaries: pass pre-injected math through unchanged,
    # apply token processing only to the plain text segments in between.
    out: list[str] = []
    pos = 0
    for m in _INLINE_MATH_RE.finditer(s):
        if m.start() > pos:
            out.append(_process_plain_segment(s[pos:m.start()]))
        out.append(m.group(0))
        pos = m.end()
    if pos < len(s):
        out.append(_process_plain_segment(s[pos:]))

    return "".join(out)


def has_latex_math_content(latex: str) -> bool:
    """True if the fragment contains inline math (fractions or symbol macros)."""
    return r"\(" in latex or r"\frac" in latex


def build_latex_for_question(question: str, options: Dict[str, str]) -> tuple[str | None, Dict[str, str | None]]:
    """
    Build LaTeX strings for the stem and each option.

    Returns ``(question_latex, options_latex)`` where values are ``None`` when the
    string has no math content (plain text only — clients can use ``question``).
    """
    q_tex = plain_to_latex_mixed(question)
    q_out: str | None = q_tex if has_latex_math_content(q_tex) else None

    opt_out: Dict[str, str | None] = {}
    for k, v in options.items():
        t = plain_to_latex_mixed(v)
        opt_out[k] = t if has_latex_math_content(t) else None

    return q_out, opt_out


def options_latex_for_persist(options_latex: Dict[str, str | None]) -> Dict[str, str]:
    """Drop None entries for MongoDB / JSON (only store keys that need LaTeX)."""
    return {k: v for k, v in options_latex.items() if v is not None}
