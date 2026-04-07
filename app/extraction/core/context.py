"""
Pipeline context definitions.

``PipelineConfig``
    Immutable configuration resolved *before* any handler runs: the open PDF
    document, the detected subject, exam type, and capability profile.  Passed
    into each handler as read-only inputs.

``ExtractionContext``
    Lean internal scratchpad used exclusively by ``ResolverChain`` strategies.
    Handlers construct a local instance of this as needed and pass it to a chain;
    it is never shared across handler boundaries.  It carries only the fields
    that resolver strategies actually access.

The previous design placed all intermediate handler outputs (``pages``,
``image_map``, ``year_sections``, ``answer_key``, ``questions``) here as well.
Those now live as typed ``*Output`` dataclasses in ``stages.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.extraction.core.profile import CapabilityProfile


@dataclass
class PipelineConfig:
    """
    Pre-handler configuration — resolved once and passed (read-only) to handlers.

    Handlers receive this alongside their typed inputs; they MUST NOT mutate it.
    """

    pdf_path: Path
    doc: Any  # fitz.Document — typed as Any to avoid a hard import at module level
    subject_override: str | None = None
    subject: str = ""
    exam_type: str = "JAMB"
    profile: "CapabilityProfile | None" = None


@dataclass
class ExtractionContext:
    """
    Internal resolver scratchpad.

    Created locally by individual handlers when they need to invoke a
    ``ResolverChain``.  Never shared across handler boundaries.

    Fields mirror what resolver strategies expect via ``ctx.*`` attribute access:

    * ``pdf_path``, ``doc``, ``subject_override``, ``subject``, ``exam_type``
      — copied from ``PipelineConfig`` when constructing a local instance.
    * ``pages`` — text pages, used by ``AnswerKeyHandler``'s resolver chain.
    * ``image_map`` — image map, used by ``QuestionExtractorHandler``'s resolver.
    * ``_active_q_text``, ``_active_year``, ``_active_answers``
      — temporary staging set by ``QuestionExtractorHandler`` before each
        ``chain.resolve()`` call; cleared immediately after.
    """

    # ── Copied from PipelineConfig ───────────────────────────────────────────
    pdf_path: Path
    doc: Any  # fitz.Document or None
    subject_override: str | None = None
    subject: str = ""
    exam_type: str = "JAMB"
    profile: "CapabilityProfile | None" = None

    # ── Set by AnswerKeyHandler before calling its resolver chain ────────────
    pages: list[dict] = field(default_factory=list)

    # ── Set by QuestionExtractorHandler before calling its resolver chain ────
    image_map: dict = field(default_factory=dict)

    # ── Temporary per-section staging (QuestionExtractorHandler only) ────────
    _active_q_text: str = ""
    _active_year: str | None = None
    _active_answers: dict[int, str] = field(default_factory=dict)
