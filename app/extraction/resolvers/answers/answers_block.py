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
    r"(?:UTME|JAMB)\s+(\d{4})\s+[A-Z]+\s+QUESTIONS\b|"
    r"(\d{4})\s+(?:UTME|JAMB)\s+[A-Z]+\s+QUESTIONS\b",
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

# Real answer-key headers: line-anchored "ANSWER KEY(S):" — avoids matching
# "answer" inside "Use the diagram below to answer…" or cover titles ("Answers").
_ANS_MARKER_RE = re.compile(
    r"(?:\n|^)[ \t]*ANSWER(?:S)?\s+KEYS?\s*:\s*",
    re.IGNORECASE,
)
# Stray headers without a colon (e.g. page breaks) — only when the next non-empty
# line looks like numbered answer data.
_ANS_MARKER_NO_COLON_RE = re.compile(
    r"(?:\n|^)[ \t]*ANSWER(?:S)?\s+KEYS?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_NEXT_LINE_ANSWERISH_RE = re.compile(
    r"^\s*(?:\d+\.\s*|\d+\.\s*[A-Da-d]|\d+\s+[A-Da-d])",
    re.IGNORECASE,
)

# Lines that belong to the ANSWERS block header (skip when scanning answer data).
_HDR_LINE_RE = re.compile(
    r"^(?:ANSWER(?:S)?(?:[ \t]+KEY(?:S)?)?|TO|JAMB|UTME|KEY(?:S)?|[A-Z]{2,})$",
    re.IGNORECASE,
)
_YEAR_ONLY_RE = re.compile(r"^\d{4}$")
# Standalone 1–3 digit lines (PDF page footers) between keys and the next year.
_PAGE_FOOTER_NUM_RE = re.compile(r"^\d{1,3}$")


def strip_noise(text: str) -> str:
    return _NOISE_RE.sub("", text)


def normalise_year_banners(text: str) -> str:
    """Replace year banners with recoverable ``__YR__YYYY`` tokens."""
    text = _JUPEB_YR_BANNER_RE.sub(r"\n__YR__\1\n", text)
    
    # Handle both (UTME YYYY) and (YYYY JAMB) groups from the updated regex
    def yr_replace(m):
        year = m.group(1) or m.group(2)
        return f"\n__YR__{year}\n"

    text = _YR_BANNER_RE.sub(yr_replace, text)
    text = _YR_BANNER_ALT_RE.sub(r"\n__YR__\1\n", text)
    return text


def _collapse_split_answer_lines(block: str) -> str:
    """Join ``N.`` and a letter on the next line (common PDF line-break artefact)."""
    return re.sub(r"(\d+)\.\s*\n\s*([A-Da-d])\b", r"\1. \2", block)


def _answer_marker_positions(text: str) -> list[int]:
    """All ANSWER KEY section starts: colon headers plus vetted no-colon headers."""
    seen: set[int] = set()
    out: list[int] = []
    for m in _ANS_MARKER_RE.finditer(text):
        seen.add(m.start())
        out.append(m.start())
    for m in _ANS_MARKER_NO_COLON_RE.finditer(text):
        pos = m.start()
        if pos in seen:
            continue
        rest = text[m.end() :]
        nxt = ""
        for ln in rest.split("\n"):
            s = ln.strip()
            if s:
                nxt = s
                break
        if nxt and _NEXT_LINE_ANSWERISH_RE.match(nxt):
            seen.add(pos)
            out.append(pos)
    return sorted(out)


def _scan_answer_block_end(text: str, start: int) -> int:
    """
    Return the offset in *text* just after the last line of answer data for the
    block that begins at *start*.

    Primary strategy: year banners are normalised to ``\\n__YR__YYYY\\n``; the
    next such token after an ANSWER KEYS header ends the answer block. Fallback:
    line walk with split-line and page-number handling for the final section.
    """
    tail = text[start:]
    yr_after = re.search(r"\n__YR__\d{4}\n", tail)
    if yr_after:
        return start + yr_after.start()
    return _scan_answer_block_end_fallback(text, start)


def _scan_answer_block_end_fallback(text: str, start: int) -> int:
    """Last answer section (no following ``__YR__``): walk lines until non-answer content."""
    rest = text[start:]
    char_pos = 0
    last_answer_end = start
    found_answers = False
    lines = rest.split("\n")

    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line_len = len(raw_line) + 1
        stripped = raw_line.strip()

        if not stripped:
            char_pos += line_len
            i += 1
            continue

        if stripped.startswith("__YR__"):
            break

        if _HDR_LINE_RE.match(stripped) or _YEAR_ONLY_RE.match(stripped):
            char_pos += line_len
            i += 1
            continue

        if _PAGE_FOOTER_NUM_RE.match(stripped):
            char_pos += line_len
            i += 1
            continue

        split_pair = False
        merged = stripped
        if re.match(r"^\d+\.\s*$", stripped) and i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt and re.match(r"^[A-Da-d]\b", nxt):
                merged = f"{stripped.strip()} {nxt[0]}"
                split_pair = True

        remainder = re.sub(r"\d+\.[ \t]*[A-Da-d]", "", merged).strip()
        if not remainder:
            found_answers = True
            if split_pair:
                last_answer_end = start + char_pos + len(raw_line) + len(lines[i + 1]) + 1
                char_pos += len(raw_line) + 1 + len(lines[i + 1]) + 1
                i += 2
            else:
                last_answer_end = start + char_pos + len(raw_line)
                char_pos += line_len
                i += 1
            continue
        if found_answers:
            break

        char_pos += line_len
        i += 1

    return last_answer_end


def extract_answer_key(block: str) -> dict[int, str]:
    """
    Parse ``{question_number: letter}`` from an ANSWERS section string.

    Handles inline format ``"1. B 2. C 3. A"``, packed ``"10.D 11.A"``, and
    letters on the line below ``N.``; also ``12 C`` (missing dot) after collapse.
    """
    block = _collapse_split_answer_lines(block)
    answers: dict[int, str] = {}
    for m in re.finditer(r"(\d+)\.[ \t]*([A-Da-d])\b", block):
        answers[int(m.group(1))] = m.group(2).upper()
    for m in re.finditer(r"(?<![.\d])(\d{1,3})\s+([A-Da-d])\b", block):
        n = int(m.group(1))
        if n not in answers:
            answers[n] = m.group(2).upper()
    return answers


YearSections = list[tuple[Optional[str], str, dict[int, str]]]

_YR_TOKEN_SPLIT_RE = re.compile(r"\n__YR__(\d{4})\n")


def _year_segments_from_q_chunk(q_chunk: str) -> list[tuple[Optional[str], str]]:
    """
    Split *q_chunk* (text before an ANSWER block) into one body per ``__YR__`` banner.

    Preamble before the first banner is prepended to the first segment (cover noise
    + first year's questions).
    """
    ms = list(_YR_TOKEN_SPLIT_RE.finditer(q_chunk))
    if not ms:
        return [(None, q_chunk)]
    out: list[tuple[Optional[str], str]] = []
    preamble = q_chunk[: ms[0].start()]
    for i, m in enumerate(ms):
        year_str = m.group(1)
        a = m.end()
        b = ms[i + 1].start() if i + 1 < len(ms) else len(q_chunk)
        body = q_chunk[a:b]
        if i == 0 and preamble.strip():
            body = preamble + body
        out.append((year_str, body))
    return out


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

        ans_positions = _answer_marker_positions(all_text)

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
            answers = extract_answer_key(a_chunk)
            segs = _year_segments_from_q_chunk(q_chunk)
            n_seg = len(segs)

            for j, (seg_year, seg_body) in enumerate(segs):
                year: str | None = seg_year

                yr_in_ans = re.search(r"JAMB\s+(\d{4})\b", a_chunk, re.IGNORECASE)
                if yr_in_ans and n_seg == 1:
                    year = yr_in_ans.group(1)
                elif year is None and n_seg == 1:
                    yr_token = re.search(r"__YR__(\d{4})", q_chunk)
                    if yr_token:
                        year = yr_token.group(1)

                q_clean = re.sub(r"\n__YR__\d+\n", "\n", seg_body)
                seg_answers = answers if (a_chunk.strip() and j == n_seg - 1) else {}
                sections.append((year, q_clean, seg_answers))

        return sections if sections else None
