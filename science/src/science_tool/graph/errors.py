"""Load-path errors for the unified entity model."""

from __future__ import annotations

from collections.abc import Iterable

from science_model.source_ref import SourceRef


class ContributionConflictError(ValueError):
    """Raised when two contributions to one entity disagree on a field.

    Takes the conflict's parts, never a preformatted message: a caller free to pass a string
    is a caller free to raise a conflict that names no file, and the arbitration is the only
    thing that still knows which sources disagreed.
    """

    def __init__(
        self, *, canonical_id: str, field: str, refs: Iterable[SourceRef]
    ) -> None:
        self.canonical_id = canonical_id
        self.field = field
        # Sorted, so one conflict reads the same on every run regardless of adapter order.
        self.refs = tuple(sorted(refs, key=lambda ref: (ref.path, ref.line or -1, ref.adapter_name)))
        if not self.refs:
            raise ValueError("a contribution conflict must name the sources that disagree")
        listed = "\n".join(f"  - {ref}" for ref in self.refs)
        super().__init__(
            f"conflicting contributions for {field!r} on entity {canonical_id!r}:\n"
            f"{listed}\n"
            f"Resolve by removing the field from all but one source."
        )


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
