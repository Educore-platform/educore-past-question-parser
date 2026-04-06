"""
Extract answer keys from the trailing ANSWERS section found in JAMB PDFs.

Also owns the full-text preprocessing step (noise stripping + year-banner
normalisation) because that logic gates which text reaches the question parser.

Returns
-------
``list[tuple[str | None, str, dict[int, str]]]``
    A list of ``(year, question_text, {q_num: answer_letter})`` tuples, one per
    year section found in the document.  When no ANSWERS sections are present the
    chain falls back to a single ``(None, full_text, {})`` tuple.
"""

from __future__ import annotations

import re
from typing import Optional

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext
from app.extraction.resolvers.subject.first_page_keyword import KNOWN_SUBJECTS

# Per-page watermark noise (e.g. www.toppers.com.ng).
# Use [ \t]* so newlines immediately after the URL are preserved.
_NOISE_RE = re.compile(r"\bwww\.\S+\b[ \t]*")

# Year-section banners: "2010 JAMB BIOLOGY QUESTIONS" → "__YR__2010"
_YR_BANNER_RE = re.compile(
    r"(\d{4})\s+JAMB\s+[A-Z]+\s+QUESTIONS\b",
    re.IGNORECASE,
)

# Alternative year-section headers: "Mathematics 1983", "Biology 1990" → "__YR__YYYY"
# Anchored to KNOWN_SUBJECTS to avoid matching arbitrary "Word YYYY" patterns.
_subjects_alt = "|".join(re.escape(s) for s in KNOWN_SUBJECTS)
_YR_BANNER_ALT_RE = re.compile(
    rf"^(?:{_subjects_alt})\s+(\d{{4}})\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# JUPEB year-section headers spanning two lines:
#   "JOINT UNIVERSITIES PRELIMINARY EXAMINATIONS BOARD"
#   "AUGUST 2024 EXAMINATIONS"
# Both lines are collapsed into a single "__YR__YYYY" token.
_JUPEB_YR_BANNER_RE = re.compile(
    r"JOINT\s+UNIVERSITIES\s+PRELIMINARY\s+EXAMINATIONS\s+BOARD[^\n]*\n[^\n]*?(\d{4})\s+EXAMINATIONS[^\n]*",
    re.IGNORECASE,
)

# ANSWERS / ANSWER KEY / ANSWER KEYS section header on its own line.
_ANS_MARKER_RE = re.compile(
    r"\nANSWER(?:S)?(?:\s+KEYS?)?\s*:?\s*\n",
    re.IGNORECASE,
)

# Lines that belong to the ANSWERS block header (skip when scanning answer data).
_HDR_LINE_RE = re.compile(
    r"^(?:ANSWER(?:S)?(?:[ \t]+KEY(?:S)?)?|TO|JAMB|KEY(?:S)?|[A-Z]{2,})$",
    re.IGNORECASE,
)
_YEAR_ONLY_RE = re.compile(r"^\d{4}$")


def strip_noise(text: str) -> str:
    return _NOISE_RE.sub("", text)


def normalise_year_banners(text: str) -> str:
    """Replace year banners with recoverable ``__YR__YYYY`` tokens.

    Handles:
    - Standard JAMB: ``YYYY JAMB SUBJECT QUESTIONS``
    - Inline subject header: ``Mathematics 1983``
    - JUPEB two-line header: ``JOINT UNIVERSITIES PRELIMINARY EXAMINATIONS BOARD``
      followed by ``AUGUST 2024 EXAMINATIONS``
    """
    text = _JUPEB_YR_BANNER_RE.sub(r"\n__YR__\1\n", text)
    text = _YR_BANNER_RE.sub(r"\n__YR__\1\n", text)
    text = _YR_BANNER_ALT_RE.sub(r"\n__YR__\1\n", text)
    return text


def _scan_answer_block_end(text: str, start: int) -> int:
    """
    Walk lines forward from *start* (position of the ANSWERS marker) and return
    the offset in *text* just after the last answer-data line.
    """
    rest = text[start:]
    char_pos = 0
    last_answer_end = start
    found_answers = False

    for raw_line in rest.split("\n"):
        line_len = len(raw_line) + 1
        stripped = raw_line.strip()

        if not stripped:
            char_pos += line_len
            continue

        if _HDR_LINE_RE.match(stripped) or _YEAR_ONLY_RE.match(stripped):
            char_pos += line_len
            continue

        remainder = re.sub(r"\d+\.[ \t]*[A-Da-d]", "", raw_line).strip()
        if not remainder:
            last_answer_end = start + char_pos + len(raw_line)
            found_answers = True
        elif found_answers:
            break

        char_pos += line_len

    return last_answer_end


def extract_answer_key(block: str) -> dict[int, str]:
    """
    Parse ``{question_number: letter}`` from an ANSWERS section string.

    Handles inline format ``"1. B 2. C 3. A"`` and packed ``"10.D 11.A"``.
    """
    answers: dict[int, str] = {}
    for m in re.finditer(r"(\d+)\.[ \t]*([A-Da-d])\b", block):
        answers[int(m.group(1))] = m.group(2).upper()
    return answers


YearSections = list[tuple[Optional[str], str, dict[int, str]]]


class AnswersBlockStrategy(BaseResolverStrategy[YearSections]):
    """
    Locate trailing ANSWERS sections, split the document text into per-year
    ``(year, q_text, answer_dict)`` tuples, and return them.

    Returns ``None`` only if ``ctx.pages`` is empty (shouldn't happen in practice).
    """

    def can_handle(self, ctx: ExtractionContext) -> bool:
        return bool(ctx.pages)

    def extract(self, ctx: ExtractionContext) -> YearSections | None:
        raw = "\n".join(strip_noise(p["text"]) for p in ctx.pages)
        all_text = normalise_year_banners(raw)

        ans_positions = [m.start() for m in _ANS_MARKER_RE.finditer(all_text)]

        if not ans_positions:
            # If year tokens exist (e.g. "Mathematics 1983" headers with no
            # trailing ANSWERS section), split the text by those tokens so each
            # year's questions receive the correct year label.
            yr_positions = [(m.start(), m.group(1)) for m in re.finditer(r"\n__YR__(\d+)\n", all_text)]
            if yr_positions:
                sections: YearSections = []
                for i, (pos, year_str) in enumerate(yr_positions):
                    chunk_start = pos + len(f"\n__YR__{year_str}\n")
                    chunk_end = yr_positions[i + 1][0] if i + 1 < len(yr_positions) else len(all_text)
                    chunk = all_text[chunk_start:chunk_end]
                    q_clean = re.sub(r"\n__YR__\d+\n", "\n", chunk)
                    sections.append((year_str, q_clean, {}))
                return sections if sections else None
            clean = re.sub(r"\n__YR__\d+\n", "\n", all_text)
            return [(None, clean, {})]

        chunks: list[tuple[str, str]] = []
        prev = 0
        for ans_pos in ans_positions:
            q_chunk = all_text[prev:ans_pos]
            ans_end = _scan_answer_block_end(all_text, ans_pos)
            if ans_end <= ans_pos:
                ans_end = ans_pos + 50
            a_chunk = all_text[ans_pos:ans_end]
            chunks.append((q_chunk, a_chunk))
            prev = ans_end

        if prev < len(all_text):
            chunks.append((all_text[prev:], ""))

        sections: YearSections = []
        for q_chunk, a_chunk in chunks:
            year: str | None = None

            yr_in_ans = re.search(r"JAMB\s+(\d{4})\b", a_chunk, re.IGNORECASE)
            if yr_in_ans:
                year = yr_in_ans.group(1)

            if year is None:
                yr_token = re.search(r"__YR__(\d{4})", q_chunk)
                if yr_token:
                    year = yr_token.group(1)

            q_clean = re.sub(r"\n__YR__\d+\n", "\n", q_chunk)
            answers = extract_answer_key(a_chunk)
            sections.append((year, q_clean, answers))

        return sections if sections else None
