"""
Chain configurations per subject.

Each dict maps a subject name (lowercase) or ``"__default__"`` to the
``ResolverChain`` that should be used for that extraction target.  Handlers look
up the right chain via ``CHAINS.get(ctx.subject.lower(), CHAINS["__default__"])``.

Adding support for a new subject or question format means:
1. Add a chain entry here (or use ``.plug()`` to extend the default).
2. Register any new strategy in the chain.
3. Nothing else in the system needs to change.
"""

from __future__ import annotations

from app.extraction.core.chain import ResolverChain

# ── Subject chains ──────────────────────────────────────────────────────────
from app.extraction.resolvers.subject.first_page_keyword import FirstPageKeywordStrategy
from app.extraction.resolvers.subject.filename import FileNameStrategy
from app.extraction.resolvers.subject.manual_override import ManualOverrideStrategy
from app.extraction.resolvers.subject.metadata import MetadataStrategy
from app.extraction.resolvers.subject.title_banner import TitleBannerStrategy
from app.extraction.resolvers.subject.subject_year_banner import SubjectYearBannerStrategy

SUBJECT_CHAINS: dict[str, ResolverChain] = {
    "__default__": ResolverChain[str](
        [
            ManualOverrideStrategy(),
            TitleBannerStrategy(),
            SubjectYearBannerStrategy(),
            FileNameStrategy(),
            MetadataStrategy(),
            FirstPageKeywordStrategy(),
        ]
    )
}

# ── Question chains ──────────────────────────────────────────────────────────
from app.extraction.resolvers.questions.bold_header import BoldHeaderStrategy
from app.extraction.resolvers.questions.numbered_list import NumberedListStrategy
from app.extraction.resolvers.questions.passage_group import PassageGroupStrategy
from app.extraction.resolvers.questions.year_section import YearSectionStrategy

QUESTION_CHAINS: dict[str, ResolverChain] = {
    "__default__": ResolverChain(
        [NumberedListStrategy(), YearSectionStrategy(), BoldHeaderStrategy()]
    ),
    "literature": ResolverChain(
        [PassageGroupStrategy(), NumberedListStrategy()]
    ),
}

# ── Option chains ────────────────────────────────────────────────────────────
from app.extraction.resolvers.options.bracketed import BracketedStrategy
from app.extraction.resolvers.options.inline import InlineStrategy
from app.extraction.resolvers.options.matrix_option import MatrixOptionStrategy
from app.extraction.resolvers.options.number_base_option import NumberBaseOptionStrategy
from app.extraction.resolvers.options.single_column import SingleColumnStrategy
from app.extraction.resolvers.options.two_column_grid import TwoColumnGridStrategy

OPTION_CHAINS: dict[str, ResolverChain] = {
    "__default__": ResolverChain(
        [TwoColumnGridStrategy(), SingleColumnStrategy(), BracketedStrategy(), InlineStrategy()]
    ),
    "mathematics": ResolverChain(
        [
            TwoColumnGridStrategy(),
            MatrixOptionStrategy(),
            NumberBaseOptionStrategy(),
            SingleColumnStrategy(),
        ]
    ),
    "further mathematics": ResolverChain(
        [
            TwoColumnGridStrategy(),
            MatrixOptionStrategy(),
            NumberBaseOptionStrategy(),
            SingleColumnStrategy(),
        ]
    ),
    "physics": ResolverChain(
        [TwoColumnGridStrategy(), MatrixOptionStrategy(), SingleColumnStrategy()]
    ),
}

# ── Answer-key chains ────────────────────────────────────────────────────────
from app.extraction.resolvers.answers.answers_block import AnswersBlockStrategy
from app.extraction.resolvers.answers.inline_answer import InlineAnswerStrategy
from app.extraction.resolvers.answers.separate_sheet import SeparateSheetStrategy

ANSWER_CHAINS: dict[str, ResolverChain] = {
    "__default__": ResolverChain(
        [AnswersBlockStrategy(), InlineAnswerStrategy(), SeparateSheetStrategy()]
    ),
}
