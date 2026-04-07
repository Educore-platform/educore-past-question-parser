"""
Pipeline orchestrator.

Exposes a single public entry-point:
``run_pipeline(pdf_path, subject_override=None, exam_type_override=None)``.

Execution order
---------------
1. Open the PDF with PyMuPDF and create an ``ExtractionContext``.
2. Run the ``SubjectResolverChain`` (uses ``ctx.doc`` directly — no pages needed yet).
3. Load the ``CapabilityProfile`` for the detected subject.
4. Build a filtered handler list from the profile using ``PipelineBuilder``.
5. Execute each handler in order; every handler reads from and writes back to ``ctx``.
6. Close the PDF doc and return ``ctx.questions``.

Handler execution order (controlled by ``PipelineBuilder._HANDLERS`` list):

    TextExtractorHandler      — always; populates ctx.pages
    ImageExtractorHandler     — has_images; populates ctx.image_map
    AnswerKeyHandler          — always; populates ctx.year_sections + ctx.answer_key
    QuestionExtractorHandler  — always; populates ctx.questions
    LatexEnricherHandler      — has_formulas; enriches ctx.questions in-place
    VectorOCRRepairerHandler  — has_ocr_vectors; (stub)
    DentalFormulaHandler      — special: dental_formula
    MatrixQuestionHandler     — special: matrix  (stub; enricher already handles)
    NumberBaseHandler         — special: number_base  (stub; enricher already handles)
    LogarithmHandler          — special: logarithm  (stub)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Return value of ``run_pipeline``."""

    questions: list[dict] = field(default_factory=list)
    total_pages: int = 0
    subject: str = ""


# ── Handler imports ──────────────────────────────────────────────────────────

from app.extraction.handlers.text_extractor import TextExtractorHandler
from app.extraction.handlers.answer_key import AnswerKeyHandler
from app.extraction.handlers.question_extractor import QuestionExtractorHandler
from app.extraction.handlers.image.extractor import ImageExtractorHandler
from app.extraction.handlers.enrichment.latex import LatexEnricherHandler
from app.extraction.handlers.enrichment.ocr_repair import VectorOCRRepairerHandler
from app.extraction.handlers.special.dental_formula import DentalFormulaHandler
from app.extraction.handlers.special.matrix import MatrixQuestionHandler
from app.extraction.handlers.special.number_base import NumberBaseHandler
from app.extraction.handlers.special.logarithm import LogarithmHandler

# ── Profile / chain imports ──────────────────────────────────────────────────

from app.extraction.core.context import ExtractionContext
from app.extraction.core.profile import CapabilityProfile
from app.extraction.profiles.capabilities import PROFILES
from app.extraction.profiles.chains import SUBJECT_CHAINS


class PipelineBuilder:
    """
    Filters the global handler list to only those handlers whose ``can_handle``
    returns ``True`` for the given profile.

    Order matters: handlers are tried in the order they appear in ``_HANDLERS``.
    """

    _HANDLERS: list[Any] = [
        TextExtractorHandler(),
        ImageExtractorHandler(),
        AnswerKeyHandler(),
        QuestionExtractorHandler(),
        LatexEnricherHandler(),
        VectorOCRRepairerHandler(),
        DentalFormulaHandler(),
        MatrixQuestionHandler(),
        NumberBaseHandler(),
        LogarithmHandler(),
    ]

    def build(self, profile: CapabilityProfile) -> list[Any]:
        return [h for h in self._HANDLERS if h.can_handle(profile)]


def run_pipeline(
    pdf_path: Path,
    *,
    subject_override: str | None = None,
    exam_type_override: str | None = None,
) -> PipelineResult:
    """
    Extract structured questions from a JAMB-style PDF.

    Parameters
    ----------
    pdf_path:
        Path to the uploaded PDF file on disk.
    subject_override:
        When provided (e.g. passed via an API query param), skips all subject
        detection strategies and uses this value directly.
    exam_type_override:
        When provided (e.g. via API), skips automatic exam-type detection and
        sets ``ctx.exam_type`` to this value for every extracted question.

    Returns
    -------
    PipelineResult
        Contains ``questions`` (list of parsed question dicts), ``total_pages``,
        and the resolved ``subject`` string.
    """
    import fitz  # PyMuPDF — import deferred so the module loads without fitz installed

    doc = fitz.open(str(pdf_path))
    try:
        ctx = ExtractionContext(
            pdf_path=pdf_path,
            doc=doc,
            subject_override=subject_override,
        )

        # ── 1. Resolve subject ───────────────────────────────────────────────
        subject_chain = SUBJECT_CHAINS["__default__"]
        subject_result = subject_chain.resolve(ctx)
        ctx.subject = subject_result.value or "unknown"
        logger.debug(
            "Subject resolved to %r by %s", ctx.subject, subject_result.resolved_by
        )

        # ── 1b. Exam type: API override, else first-page heuristics ───────────
        override = (exam_type_override or "").strip()
        if override:
            ctx.exam_type = override
            logger.debug("Exam type from override: %s", ctx.exam_type)
        elif len(doc) > 0 and "JOINT UNIVERSITIES PRELIMINARY EXAMINATIONS BOARD" in doc[0].get_text().upper():
            ctx.exam_type = "JUPEB"
            logger.debug("Exam type detected: JUPEB")

        # ── 2. Load capability profile ───────────────────────────────────────
        ctx.profile = PROFILES.get(ctx.subject.lower(), PROFILES["__default__"])
        logger.debug("Profile: %s", ctx.profile)

        # ── 3. Run filtered handler pipeline ────────────────────────────────
        for handler in PipelineBuilder().build(ctx.profile):
            ctx = handler.process(ctx)
            logger.debug(
                "%s finished — %d questions so far",
                type(handler).__name__,
                len(ctx.questions),
            )

    finally:
        doc.close()

    return PipelineResult(
        questions=ctx.questions,
        total_pages=len(ctx.pages),
        subject=ctx.subject,
    )
