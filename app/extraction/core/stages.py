"""
Typed stage output dataclasses for the extraction pipeline.

Each handler declares what it produces via one of these frozen dataclasses.
The pipeline orchestrator (``run_pipeline``) wires them together explicitly
instead of threading a single shared mutable bag through every handler.

Immutability (``frozen=True``) makes the data-flow direction clear: every
handler consumes its declared inputs and returns a new output — no side-effects
on a shared object.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextExtractionOutput:
    """Output of ``TextExtractorHandler``.

    ``pages`` is a list of ``{"page": int, "text": str}`` dicts, one per PDF page.
    """

    pages: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ImageExtractionOutput:
    """Output of ``ImageExtractorHandler``.

    ``image_map`` maps ``(year, question_number)`` tuples to ``"/images/<filename>"`` URLs.
    An empty dict is returned when the profile has no images.
    """

    image_map: dict = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerKeyOutput:
    """Output of ``AnswerKeyHandler``.

    ``year_sections`` is a list of ``(year, question_block_text, {q_num: answer_letter})``
    tuples, one per detected year section.

    ``answer_key`` is a flat ``{(year, q_num): letter}`` convenience map built from
    ``year_sections``.
    """

    year_sections: list = field(default_factory=list)
    answer_key: dict = field(default_factory=dict)


@dataclass(frozen=True)
class QuestionExtractionOutput:
    """
    Output of ``QuestionExtractorHandler`` and every downstream enrichment handler
    (``LatexEnricherHandler``, ``DentalFormulaHandler``, and stubs).

    ``questions`` is the list of parsed question dicts, potentially enriched with
    ``question_latex``, ``options_latex``, and repaired option text by the time the
    pipeline completes.
    """

    questions: list[dict] = field(default_factory=list)
