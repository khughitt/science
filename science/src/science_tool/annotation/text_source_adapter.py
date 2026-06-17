# science/src/science_tool/annotation/text_source_adapter.py
"""Source adapters — turn a specific kind of text source into source-neutral
annotation candidates (the text-layer side of the prose-epistemics seam).

Mirrors the StorageAdapter "declared-policy, no-isinstance" pattern
(graph/storage_adapters/base.py): capabilities are class attributes and
polymorphic methods; dispatch is a registry list + first-match.
"""

from __future__ import annotations

from enum import Enum


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
