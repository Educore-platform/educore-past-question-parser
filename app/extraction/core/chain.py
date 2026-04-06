"""
Chain-of-Responsibility infrastructure for the extraction pipeline.

Every extraction target (subject, questions, options, answers) has a
``ResolverChain`` — an ordered list of strategies tried in sequence until one
succeeds.  Strategies declare via ``can_handle`` whether they are willing to
attempt extraction given the current context, and return ``None`` from
``extract`` when they cannot produce a result.

Usage
-----
::

    chain = ResolverChain([StrategyA(), StrategyB(), StrategyC()])
    result = chain.resolve(ctx)
    if not result.failed:
        print(result.value, "resolved by", result.resolved_by)

    # Insert a high-priority strategy without rebuilding the whole chain:
    chain2 = chain.plug(MyCustomStrategy(), at=0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from app.extraction.core.context import ExtractionContext

T = TypeVar("T")


class BaseResolverStrategy(Generic[T]):
    """
    Convenience base class for resolver strategies.

    Subclasses must override ``extract``; ``can_handle`` defaults to always
    returning ``True`` (i.e. the strategy is always willing to attempt
    extraction).  Override ``can_handle`` to add a cheap pre-flight guard.
    """

    @property
    def name(self) -> str:
        return type(self).__name__

    def can_handle(self, ctx: ExtractionContext) -> bool:  # noqa: ARG002
        return True

    def extract(self, ctx: ExtractionContext) -> T | None:
        raise NotImplementedError(f"{self.name}.extract() is not implemented")


@dataclass
class ResolverResult(Generic[T]):
    """Result wrapper that carries which strategy succeeded — useful for debugging."""

    value: T | None
    resolved_by: str | None  # strategy name that produced the result, or None on failure
    failed: bool = False


class ResolverChain(Generic[T]):
    """
    Ordered chain of strategies.  The first strategy that passes ``can_handle``
    *and* returns a non-``None`` value from ``extract`` wins.

    The chain is immutable; ``plug`` returns a new chain.
    """

    def __init__(self, strategies: list[BaseResolverStrategy[T]]) -> None:
        self._strategies: list[BaseResolverStrategy[T]] = list(strategies)

    def resolve(self, ctx: ExtractionContext) -> ResolverResult[T]:
        for strategy in self._strategies:
            if not strategy.can_handle(ctx):
                continue
            result = strategy.extract(ctx)
            if result is not None:
                return ResolverResult(value=result, resolved_by=strategy.name, failed=False)
        return ResolverResult(value=None, resolved_by=None, failed=True)

    def plug(self, strategy: BaseResolverStrategy[T], *, at: int = 0) -> ResolverChain[T]:
        """Return a new chain with *strategy* inserted at *at* (default: front = highest priority)."""
        new = list(self._strategies)
        new.insert(at, strategy)
        return ResolverChain(new)
