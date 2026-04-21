"""Load-path errors for the unified entity model."""

from __future__ import annotations

from science_model.source_ref import SourceRef


class EntityIdentityCollisionError(ValueError):
    """Raised when two storage adapters produce records with the same canonical_id."""

    def __init__(self, canonical_id: str, first: SourceRef, second: SourceRef) -> None:
        self.canonical_id = canonical_id
        self.first = first
        self.second = second
        super().__init__(
            f"entity {canonical_id!r} produced by multiple sources:\n"
            f"  - {first}\n"
            f"  - {second}\n"
            f"Resolve by removing one source, or migrate to a single adapter."
        )
