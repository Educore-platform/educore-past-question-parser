from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CapabilityProfile:
    """Declares what a subject requires so the pipeline can compose the right handlers."""

    has_images: bool = False
    has_formulas: bool = False
    has_ocr_vectors: bool = False
    text_layout: Literal["simple", "two_column"] = "simple"
    special_question_types: list[str] = field(default_factory=list)
