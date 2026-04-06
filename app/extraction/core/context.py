from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.extraction.core.profile import CapabilityProfile


@dataclass
class ExtractionContext:
    """
    Shared state that flows through every stage of the pipeline.

    Handlers only write to fields they own; downstream handlers read those fields.
    Fields prefixed with ``_active_`` are temporary staging slots set by a handler
    before it calls a resolver chain — they are not meaningful outside that call.
    """

    # ── Required ────────────────────────────────────────────────────────────
    pdf_path: Path
    doc: Any  # fitz.Document — typed as Any to avoid a hard import at module level

    # ── Optional override passed in via API ─────────────────────────────────
    subject_override: str | None = None

    # ── Populated by SubjectResolverChain (before pipeline) ─────────────────
    subject: str = ""
    exam_type: str = "JAMB"

    # ── Populated after subject detection ───────────────────────────────────
    profile: CapabilityProfile | None = None

    # ── Populated by TextExtractorHandler ───────────────────────────────────
    pages: list[dict] = field(default_factory=list)  # [{page: int, text: str}, ...]

    # ── Populated by ImageExtractorHandler ──────────────────────────────────
    image_map: dict = field(default_factory=dict)  # (year, q_num) -> "/images/..."

    # ── Populated by AnswerKeyHandler ────────────────────────────────────────
    # year_sections: [(year, question_text, {q_num: answer_letter})]
    year_sections: list[tuple[str | None, str, dict[int, str]]] = field(default_factory=list)
    # Flat map: (year, q_num) -> answer_letter  (convenience for post-processing)
    answer_key: dict[tuple[str | None, int], str] = field(default_factory=dict)

    # ── Populated by QuestionExtractorHandler ───────────────────────────────
    questions: list[dict] = field(default_factory=list)

    # ── Temporary state: set by QuestionExtractorHandler before calling chains
    _active_q_text: str = ""
    _active_year: str | None = None
    _active_answers: dict[int, str] = field(default_factory=dict)
