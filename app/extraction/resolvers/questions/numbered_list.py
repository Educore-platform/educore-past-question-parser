"""
Numbered-list question splitter — the primary question resolver for JAMB PDFs.

Migrated from ``_parse_section`` in ``pdf_parser.py``.  Splits a year-section
text block on ``N.`` markers and parses each question's stem and options.

The resolver reads temporary state from ``ExtractionContext``:

* ``ctx._active_q_text``  — the year-section question text
* ``ctx._active_year``    — the year string (or ``None``)
* ``ctx._active_answers`` — ``{q_num: answer_letter}`` for this section
* ``ctx.subject``         — e.g. ``"Biology"``
* ``ctx.image_map``       — ``(year, q_num) → image_url``
"""

from __future__ import annotations

import re
from typing import Optional

from app.extraction.core.chain import BaseResolverStrategy
from app.extraction.core.context import ExtractionContext

_OPT_LABEL_ONLY_RE = re.compile(r"^[A-Da-d][.)]\s*$")


def _parse_section(
    text: str,
    year: Optional[str],
    subject: str,
    answers: dict[int, str],
    image_map: Optional[dict] = None,
    exam: str = "JAMB",
) -> list[dict]:
    """
    Parse individual MCQ questions from a single year's text block.

    Handles upper- and lowercase option letters, options with no space after
    the period, and multi-line stems/option text.
    """
    questions: list[dict] = []

    blocks = re.split(r"\n(?=\d{1,3}\.)", "\n" + text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        q_match = re.match(r"^(\d{1,3})\.\s*([\s\S]+)", block)
        if not q_match:
            continue

        q_num = int(q_match.group(1))
        if q_num < 1:
            continue
        remaining = q_match.group(2)

        first_opt = re.search(r"(?:\n|\s\s+)([A-Ea-e])[.) ]\s*\S", remaining)
        if not first_opt:
            continue

        question_text = remaining[: first_opt.start()].strip()
        options_raw = "\n" + remaining[first_opt.start():]

        options: dict[str, str] = {}
        for opt_m in re.finditer(
            r"(?:\n|\s\s+)([A-Ea-e])[.) ]\s*(.*?)(?=(?:\n|\s\s+)[A-Ea-e][.) ]|\Z)",
            options_raw,
            re.DOTALL,
        ):
            letter = opt_m.group(1).upper()
            raw_lines = opt_m.group(2).strip().split("\n")
            val = "\n".join(" ".join(ln.split()) for ln in raw_lines if ln.strip())
            if val:
                options[letter] = val

        if not question_text or len(options) < 2:
            continue

        if all(_OPT_LABEL_ONLY_RE.match(v) for v in options.values()):
            continue

        image_url: Optional[str] = None
        if image_map is not None:
            image_url = image_map.get((year, q_num))

        q_plain = " ".join(question_text.split())

        questions.append(
            {
                "year": year,
                "subject": subject,
                "exam": exam,
                "question_number": q_num,
                "question": q_plain,
                "options": options,
                "answer": answers.get(q_num),
                "explanation": None,
                "image_url": image_url,
            }
        )

    return questions


class NumberedListStrategy(BaseResolverStrategy[list]):
    """
    Primary question-splitting strategy for JAMB-style PDFs.

    Reads ``ctx._active_q_text``, ``ctx._active_year``, ``ctx._active_answers``,
    ``ctx.subject``, and ``ctx.image_map`` and returns a full list of question
    dicts (including options).
    """

    def can_handle(self, ctx: ExtractionContext) -> bool:
        return bool(ctx._active_q_text)

    def extract(self, ctx: ExtractionContext) -> list | None:
        questions = _parse_section(
            text=ctx._active_q_text,
            year=ctx._active_year,
            subject=ctx.subject,
            answers=ctx._active_answers,
            image_map=ctx.image_map,
            exam=ctx.exam_type,
        )
        return questions if questions else None
