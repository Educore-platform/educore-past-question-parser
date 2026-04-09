"""
Subject capability registry.

Each entry declares what a subject needs so the pipeline can compose exactly the
right chain of handlers — nothing more, nothing less.  Unknown subjects fall back
to ``__default__``, which enables every capability (conservative but correct).
"""

from __future__ import annotations

from app.extraction.core.profile import CapabilityProfile

PROFILES: dict[str, CapabilityProfile] = {
    "biology": CapabilityProfile(
        has_images=True,
        text_layout="two_column",
        special_question_types=["dental_formula"],
    ),
    "chemistry": CapabilityProfile(
        has_images=True,
        has_formulas=True,
    ),
    "physics": CapabilityProfile(
        has_images=True,
        has_formulas=True,
        special_question_types=["matrix"],
    ),
    "mathematics": CapabilityProfile(
        has_images=True,
        has_formulas=True,
        has_ocr_vectors=True,
        text_layout="two_column",
        special_question_types=["matrix", "number_base", "logarithm"],
    ),
    "further mathematics": CapabilityProfile(
        has_images=True,
        has_formulas=True,
        has_ocr_vectors=True,
        text_layout="two_column",
        special_question_types=["matrix", "number_base", "logarithm"],
    ),
    "geography": CapabilityProfile(
        has_images=True,
    ),
    "government": CapabilityProfile(),
    "economics": CapabilityProfile(
        has_images=True,
        text_layout="two_column",
    ),
    "literature": CapabilityProfile(),
    "english": CapabilityProfile(),
    "english language": CapabilityProfile(),
    "history": CapabilityProfile(),
    "accounting": CapabilityProfile(),
    "commerce": CapabilityProfile(),
    "agriculture": CapabilityProfile(
        has_images=True,
    ),
    "crs": CapabilityProfile(),
    "irs": CapabilityProfile(),
    "computer science": CapabilityProfile(),
    # Conservative default: enables every capability so unknown subjects still work.
    "__default__": CapabilityProfile(
        has_images=True,
        has_formulas=True,
        text_layout="two_column",
        special_question_types=["matrix", "number_base", "dental_formula"],
    ),
}
