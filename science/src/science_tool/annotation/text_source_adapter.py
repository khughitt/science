# science/src/science_tool/annotation/text_source_adapter.py
"""Source adapters — turn a specific kind of text source into source-neutral
annotation candidates (the text-layer side of the prose-epistemics seam).

Mirrors the StorageAdapter "declared-policy, no-isinstance" pattern
(graph/storage_adapters/base.py): capabilities are class attributes and
polymorphic methods; dispatch is a registry list + first-match.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from science_tool.annotation.statement_extract import (
        ExtractReport,
        FigurativeCandidate,
        StatementCandidate,
    )


class LocatorRegime(Enum):
    """How an adapter locates spans in its source.

    - OFFSET_ANCHORED: oa:TextQuoteSelector + offsets + content-hash re-audit
      (the "anchoring stack"); for immutable sources (papers, books).
    - REGENERABLE: cheap heading/section + quoted-text locators, no offset/hash
      machinery; for mutable internal prose (arrives in P2).
    - NONE: candidates carry no span provenance.
    """

    OFFSET_ANCHORED = "offset_anchored"
    REGENERABLE = "regenerable"
    NONE = "none"


class TextSourceAdapter(ABC):
    """Turn one kind of text source into source-neutral annotation candidates.

    Distinct from the audit-subsystem `SourceAdapter` Protocol in
    `annotation/sources/base.py` (a lint scanner). This is the adapter for a *text
    source* (paper, book, internal prose) feeding the extract→promote pipeline.

    Subclasses MUST implement `handles()` and `source_ref()` (abstract), and SHOULD
    override `extract()` for whatever locator regime they declare. Capabilities are
    declared as class attributes so the CLI reads them instead of branching on
    adapter type (mirrors StorageAdapter, Spec 3 Slice A).
    """

    name: str  # human-readable adapter name
    locator_regime: LocatorRegime

    # Declared capabilities. P1 dispatches `extract`/`source_ref` through the
    # adapter; `fetch`/`seed` are declared for P2 (persist-source / pubtator stay
    # paper-specific until a second source needs them).
    can_fetch: bool = False
    can_seed: bool = False

    @abstractmethod
    def handles(self, source_md: Path) -> bool:
        """Return True if this adapter owns `source_md`."""
        raise NotImplementedError

    @abstractmethod
    def source_ref(self, source_md: Path) -> str:
        """The resolvable provenance ref recorded in minted entities' source_refs.

        The adapter guarantees this ref resolves to a materializable entity
        (umbrella §4.1).
        """
        raise NotImplementedError

    def extract(
        self,
        *,
        source_md: Path,
        model: str,
        candidates: "list[StatementCandidate | FigurativeCandidate]",
        now: datetime,
        actor: str,
    ) -> "ExtractReport":
        """Persist agent-extracted candidates as located annotations.

        Base raises: an adapter must implement extraction for its regime.
        """
        raise NotImplementedError(
            f"adapter {self.name!r} does not implement extract "
            f"(locator_regime={self.locator_regime.value})"
        )


_SOURCE_MD_SUFFIX = ".source.md"


class PaperSourceAdapter(TextSourceAdapter):
    """The shipped paper pipeline as a TextSourceAdapter — behavior-neutral.

    Sources are `<citekey>.source.md`; locators are offset-anchored
    (oa:TextQuoteSelector); the provenance ref is `paper:<citekey>`, resolvable
    to the existing paper entity persist-source already resolved.
    """

    name = "paper"
    locator_regime = LocatorRegime.OFFSET_ANCHORED
    can_fetch = True
    can_seed = True

    def handles(self, source_md: Path) -> bool:
        return source_md.name.endswith(_SOURCE_MD_SUFFIX)

    def source_ref(self, source_md: Path) -> str:
        name = source_md.name
        if not name.endswith(_SOURCE_MD_SUFFIX):
            raise ValueError(
                f"PaperSourceAdapter.source_ref expects a {_SOURCE_MD_SUFFIX} path: {source_md}"
            )
        return f"paper:{name[: -len(_SOURCE_MD_SUFFIX)]}"

    def extract(
        self,
        *,
        source_md: Path,
        model: str,
        candidates: "list[StatementCandidate | FigurativeCandidate]",
        now: datetime,
        actor: str,
    ) -> "ExtractReport":
        # Delegate to the offset-anchored implementation; behavior-neutral.
        from science_tool.annotation.statement_extract import extract_candidates

        return extract_candidates(
            source_md=source_md,
            model=model,
            candidates=candidates,
            now=now,
            actor=actor,
        )
