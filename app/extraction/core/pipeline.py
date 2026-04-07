"""
Pipeline orchestrator.

Exposes a single public entry-point:
``run_pipeline(pdf_path, subject_override=None, exam_type_override=None)``.

Execution order
---------------
1. Open the PDF with PyMuPDF and create a ``PipelineConfig``.
2. Run the ``SubjectResolverChain`` to detect subject.
3. Detect exam type (API override or first-page JUPEB heuristic).
4. Load the ``CapabilityProfile`` for the detected subject.
5. Execute each handler in a fixed, explicit order; each handler receives only
   the typed inputs it declared and returns a typed ``*Output`` object.
6. Close the PDF doc and return ``ctx.questions`` via ``PipelineResult``.

Handler execution order and gating conditions:

    TextExtractorHandler      — always; receives (doc)
    ImageExtractorHandler     — profile.has_images; receives (doc, pdf_path)
    AnswerKeyHandler          — always; receives (pages, subject, pdf_path)
    QuestionExtractorHandler  — always; receives (year_sections, image_map, subject, pdf_path)
    LatexEnricherHandler      — profile.has_formulas; receives (questions)
    VectorOCRRepairerHandler  — profile.has_ocr_vectors; receives (questions)
    DentalFormulaHandler      — "dental_formula" in special_question_types; receives (questions, pdf_path)
    MatrixQuestionHandler     — "matrix" in special_question_types; receives (questions)
    NumberBaseHandler         — "number_base" in special_question_types; receives (questions)
    LogarithmHandler          — "logarithm" in special_question_types; receives (questions)

The shared-bag ``ExtractionContext`` is no longer passed between handlers.
Each handler receives only what it needs and returns a typed output that the
next handler may consume.  ``ExtractionContext`` remains as an internal helper
used inside ``AnswerKeyHandler`` and ``QuestionExtractorHandler`` when they call
resolver chains — it is not visible at the pipeline level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

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

from app.extraction.core.context import ExtractionContext, PipelineConfig
from app.extraction.core.profile import CapabilityProfile
from app.extraction.profiles.capabilities import PROFILES
from app.extraction.profiles.chains import SUBJECT_CHAINS

# ── Handler singletons ───────────────────────────────────────────────────────

_text_handler = TextExtractorHandler()
_image_handler = ImageExtractorHandler()
_answer_handler = AnswerKeyHandler()
_question_handler = QuestionExtractorHandler()
_latex_handler = LatexEnricherHandler()
_ocr_handler = VectorOCRRepairerHandler()
_dental_handler = DentalFormulaHandler()
_matrix_handler = MatrixQuestionHandler()
_number_base_handler = NumberBaseHandler()
_logarithm_handler = LogarithmHandler()


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
        sets ``exam_type`` to this value for every extracted question.

    Returns
    -------
    PipelineResult
        Contains ``questions`` (list of parsed question dicts), ``total_pages``,
        and the resolved ``subject`` string.
    """
    import fitz  # PyMuPDF — import deferred so the module loads without fitz installed

    doc = fitz.open(str(pdf_path))
    try:
        # ── 1. Resolve subject ───────────────────────────────────────────────
        # The subject chain still uses an ExtractionContext internally because
        # the resolver strategies access ctx.doc and ctx.subject_override.
        _subject_ctx = ExtractionContext(
            pdf_path=pdf_path,
            doc=doc,
            subject_override=subject_override,
        )
        subject_chain = SUBJECT_CHAINS["__default__"]
        subject_result = subject_chain.resolve(_subject_ctx)
        subject = subject_result.value or "unknown"
        logger.debug(
            "Subject resolved to %r by %s", subject, subject_result.resolved_by
        )

        # ── 2. Exam type: API override, else first-page heuristics ───────────
        override = (exam_type_override or "").strip()
        if override:
            exam_type = override
            logger.debug("Exam type from override: %s", exam_type)
        elif len(doc) > 0 and "JOINT UNIVERSITIES PRELIMINARY EXAMINATIONS BOARD" in doc[0].get_text().upper():
            exam_type = "JUPEB"
            logger.debug("Exam type detected: JUPEB")
        else:
            exam_type = "JAMB"

        # ── 3. Load capability profile ───────────────────────────────────────
        profile: CapabilityProfile = PROFILES.get(subject.lower(), PROFILES["__default__"])
        logger.debug("Profile: %s", profile)

        # ── 4. Run typed handler pipeline ────────────────────────────────────

        # Stage: text extraction (always)
        text_out = _text_handler.process(doc)
        logger.debug("TextExtractorHandler finished — %d pages", len(text_out.pages))

        # Stage: image extraction (gated by profile.has_images)
        if _image_handler.can_handle(profile):
            image_out = _image_handler.process(doc, pdf_path)
        else:
            from app.extraction.core.stages import ImageExtractionOutput
            image_out = ImageExtractionOutput()
        logger.debug("ImageExtractorHandler — %d images", len(image_out.image_map))

        # Stage: answer-key parsing (always)
        answer_out = _answer_handler.process(text_out.pages, subject, pdf_path)
        logger.debug(
            "AnswerKeyHandler finished — %d year sections", len(answer_out.year_sections)
        )

        # Stage: question extraction (always)
        q_out = _question_handler.process(
            answer_out.year_sections,
            image_out.image_map,
            subject,
            pdf_path,
        )
        logger.debug(
            "QuestionExtractorHandler finished — %d questions", len(q_out.questions)
        )

        # Downstream enrichment stages all receive and return a questions list.
        questions = q_out.questions

        if _latex_handler.can_handle(profile):
            questions = _latex_handler.process(questions).questions
            logger.debug("LatexEnricherHandler finished")

        if _ocr_handler.can_handle(profile):
            questions = _ocr_handler.process(questions).questions
            logger.debug("VectorOCRRepairerHandler finished")

        if _dental_handler.can_handle(profile):
            questions = _dental_handler.process(questions, pdf_path).questions
            logger.debug("DentalFormulaHandler finished")

        if _matrix_handler.can_handle(profile):
            questions = _matrix_handler.process(questions).questions
            logger.debug("MatrixQuestionHandler finished")

        if _number_base_handler.can_handle(profile):
            questions = _number_base_handler.process(questions).questions
            logger.debug("NumberBaseHandler finished")

        if _logarithm_handler.can_handle(profile):
            questions = _logarithm_handler.process(questions).questions
            logger.debug("LogarithmHandler finished")

    finally:
        doc.close()

    return PipelineResult(
        questions=questions,
        total_pages=len(text_out.pages),
        subject=subject,
    )
