"""
Two-column grid text extraction and option parsing.

JAMB maths/biology papers often arrange answer options A/B on one row and C/D on
the next, both side-by-side.  PyMuPDF's default ``get_text()`` interleaves the
columns, so this module provides:

* Low-level helpers (``_words_to_row_text``, ``_find_option_label_words``,
  ``extract_page_text_smart``) used by ``TextExtractorHandler`` to fix the layout
  at page-extraction time.

* ``TwoColumnGridStrategy`` — an option-level resolver strategy (used by
  ``QuestionExtractorHandler`` / ``OPTION_CHAINS``) that detects and returns
  already-fixed options from a question's raw text block.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List

if TYPE_CHECKING:
    import fitz

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

# Word-level option label: "A.", "B.", "C.", "D.", "E." (any case)
_OPT_WORD_RE = re.compile(r"^[A-Ea-e][.)]$")
# Safety guard: option value that is *only* another option label
_OPT_LABEL_ONLY_RE = re.compile(r"^[A-Ea-e][.)]\s*$")


# ---------------------------------------------------------------------------
# Page-level helpers
# ---------------------------------------------------------------------------

def _words_to_row_text(words: list, y_tolerance: float = 4.0) -> str:
    """
    Convert PyMuPDF word tuples into row-structured text.

    Words sharing the same y0 (±tolerance) are grouped into one row, sorted
    left-to-right.  Stacked single-digit numerator/denominator pairs that
    share the same x-column are merged as ``N/D``.
    """
    if not words:
        return ""

    sorted_w = sorted(words, key=lambda w: (w[1], w[0]))

    raw_rows: List[List[tuple]] = []
    current: List[tuple] = [sorted_w[0]]
    for w in sorted_w[1:]:
        if abs(w[1] - current[0][1]) <= y_tolerance:
            current.append(w)
        else:
            raw_rows.append(current)
            current = [w]
    raw_rows.append(current)

    merged_rows: List[List[tuple]] = []
    skip_next = False
    for i, row in enumerate(raw_rows):
        if skip_next:
            skip_next = False
            continue
        if (
            i + 1 < len(raw_rows)
            and len(row) == 1
            and len(raw_rows[i + 1]) == 1
            and row[0][4].strip().isdigit()
            and raw_rows[i + 1][0][4].strip().isdigit()
            and abs(row[0][0] - raw_rows[i + 1][0][0]) < 6
            and raw_rows[i + 1][0][1] - row[0][1] < y_tolerance * 2
        ):
            numer = row[0][4].strip()
            denom = raw_rows[i + 1][0][4].strip()
            merged = (
                row[0][0],
                row[0][1],
                row[0][2],
                raw_rows[i + 1][0][3],
                f"{numer}/{denom}",
            )
            merged_rows.append([merged])
            skip_next = True
        else:
            merged_rows.append(row)

    lines = [
        " ".join(w[4] for w in sorted(row, key=lambda w: w[0]))
        for row in merged_rows
    ]
    return "\n".join(ln for ln in lines if ln.strip())


def _find_option_label_words(page: fitz.Page) -> Dict[str, tuple]:
    """
    Scan all words on a page for option labels (A., B., C., D.) and return
    ``{letter: word_tuple}``.  When the same letter appears multiple times the
    leftmost instance is kept.
    """
    label_words: Dict[str, tuple] = {}
    for w in page.get_text("words"):
        text = w[4].strip()
        if _OPT_WORD_RE.match(text):
            letter = text[0].upper()
            if letter not in label_words or w[0] < label_words[letter][0]:
                label_words[letter] = w
    return label_words


def extract_page_text_smart(page: fitz.Page) -> str:
    """
    Extract page text with column-aware reconstruction for two-column option layouts.

    When A. and B. labels share the same y-position but sit in different horizontal
    halves, clip-rectangle extraction is used per option to preserve 2-D layout.
    Otherwise falls back to ``page.get_text()``.
    """
    import fitz as _fitz

    page_w = page.rect.width
    all_words = page.get_text("words")
    label_words = _find_option_label_words(page)

    a_w = label_words.get("A")
    b_w = label_words.get("B")
    if (
        a_w is None
        or b_w is None
        or abs(a_w[1] - b_w[1]) > 8
        or abs(a_w[0] - b_w[0]) < page_w * 0.3
    ):
        return page.get_text()

    col_split = (a_w[2] + b_w[0]) / 2
    first_opt_y = min(w[1] for w in label_words.values()) - 5

    above_text = page.get_text(clip=_fitz.Rect(0, 0, page_w, first_opt_y)).strip()

    sorted_labels = sorted(label_words.items(), key=lambda kv: (kv[1][1], kv[1][0]))
    opt_rows: List[List[tuple]] = []
    for item in sorted_labels:
        placed = False
        for row in opt_rows:
            if abs(item[1][1] - row[0][1][1]) < 8:
                row.append(item)
                placed = True
                break
        if not placed:
            opt_rows.append([item])

    option_parts: List[str] = []
    for row_idx, row in enumerate(opt_rows):
        row.sort(key=lambda kv: kv[1][0])
        row_y_top = row[0][1][1] - 5
        row_y_bottom = (
            opt_rows[row_idx + 1][0][1][1] - 5
            if row_idx + 1 < len(opt_rows)
            else page.rect.height
        )
        for _letter, word in row:
            x0 = 0.0 if word[0] < col_split else col_split
            x1 = col_split if word[0] < col_split else page_w
            clip = _fitz.Rect(x0, row_y_top, x1, row_y_bottom)
            clip_words = [
                w
                for w in all_words
                if w[0] >= clip.x0 - 2
                and w[2] <= clip.x1 + 2
                and w[1] >= clip.y0 - 2
                and w[3] <= clip.y1 + 2
            ]
            text = _words_to_row_text(clip_words)
            if text:
                option_parts.append(text)

    return above_text + ("\n" if above_text else "") + "\n".join(option_parts)


# ---------------------------------------------------------------------------
# Option-level resolver strategy
# ---------------------------------------------------------------------------

class TwoColumnGridStrategy(BaseResolverStrategy[dict]):
    """
    Parse options from a question's raw text block that has already been
    linearised by ``extract_page_text_smart``.  Handles A-D with period or
    paren delimiters, multi-line values, and matrix row content.

    This is also the default strategy for single-column layouts because the
    linearised text always has one option per line after the smart extractor runs.
    """

    def extract(self, ctx: ExtractionContext) -> dict | None:
        # ctx._active_q_text is the raw question block text set by
        # QuestionExtractorHandler before calling the option chain.
        raw = ctx._active_q_text
        if not raw:
            return None

        first_opt = re.search(r"\n([A-Ea-e])[.)]\s*\S", raw)
        if not first_opt:
            return None

        options_raw = "\n" + raw[first_opt.start():]
        options: dict[str, str] = {}
        for opt_m in re.finditer(
            r"\n([A-Ea-e])[.)]\s*(.*?)(?=\n[A-Ea-e][.)]|\Z)",
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
