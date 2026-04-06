"""
Publisher/source-specific chain overrides.

When a new PDF source (e.g. Cowbell, Waec) uses a different formatting
convention, add an entry here rather than touching any existing handler or
resolver.

Example — Cowbell PDFs use ``(i)(ii)(iii)(iv)`` option labels::

    from app.extraction.resolvers.options.roman_numeral import RomanNumeralOptionStrategy
    from app.extraction.profiles.chains import OPTION_CHAINS

    SOURCE_OVERRIDES["cowbell"] = {
        "option_chain": OPTION_CHAINS["__default__"].plug(
            RomanNumeralOptionStrategy(), at=0
        )
    }

The pipeline looks up source overrides when a ``source`` field is present on
``ExtractionContext`` (not yet wired — extend when needed).
"""

from __future__ import annotations

SOURCE_OVERRIDES: dict[str, dict] = {}
