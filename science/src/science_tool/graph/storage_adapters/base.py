"""StorageAdapter base — persistence-only contract.

Per spec §Storage Adapters: an adapter may discover files, parse
storage-specific syntax, and load records into the canonical entity
model family. It MAY NOT define entity semantics — validation belongs
to the registered entity schema.
"""

from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Any

from science_model.entities import Entity
from science_model.source_ref import SourceRef

from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.source_records import AggregateRowMeta, MarkdownSourceDocument


class StorageAdapter(ABC):
    """Abstract base class all storage adapters inherit from.

    Subclasses MUST override `discover()` and `load_raw()`. `dump()` is
    optional during migration; the default raises NotImplementedError.

    Load-time policy is declared here (Spec 3 Slice A) so the source-load loop
    reads it instead of branching on adapter type/name. The defaults below are
    the common case (an owner adapter that contributes no extra records and never
    defers); adapters override only what differs.
    """

    name: str  # human-readable adapter name; travels in SourceRef.adapter_name

    # Default participation: an adapter declares owner rows. Subclasses that
    # contribute borrower/external-reference rows override this (design §B3/§C3).
    participation_mode: ParticipationMode = ParticipationMode.OWNER

    # When True, a core entity that fails schema validation SOLELY because it is
    # missing identity fields is skipped-with-warning even under strict_core_schema,
    # instead of raising (fb-2026-05-30-008). Only MarkdownAdapter sets this.
    skip_core_on_missing_identity: bool = False

    def discover(self, project_root: Path) -> list[SourceRef]:
        """Walk `project_root` and return one SourceRef per discoverable record.

        For adapters where one file contains many records (multi-entity
        aggregates), return one SourceRef per entry — line number included
        where practical. For single-entity files, return one SourceRef per file.
        """
        raise NotImplementedError

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        """Return a registry-dispatchable raw record.

        The returned dict MUST contain a `kind` field (string) so the registry
        can resolve the target schema. All other fields become kwargs to
        `SchemaClass.model_validate(raw)`.
        """
        raise NotImplementedError

    def dump(self, entity: Entity) -> str | dict[str, Any]:
        """Serialize an entity back to this adapter's storage format.

        Optional during migration. Subclasses raise NotImplementedError if
        write support is not implemented.
        """
        raise NotImplementedError(f"adapter {self.name!r} does not support write")

    # --- load-time policy (Spec 3 Slice A) -------------------------------------

    def should_defer(self, *, already_owned: bool) -> bool:
        """Return True to contribute no owner declaration and no duplicate entity
        when this id is already owned this load.

        Default: an external-reference adapter (bib, curie-ref) defers to an
        existing owner (§B3/§C3). DatapackageAdapter overrides this — it is an
        OWNER adapter but still defers to an existing owner (§B4).
        """
        return self.participation_mode is ParticipationMode.EXTERNAL_REFERENCE and already_owned

    def source_document(self, ref: SourceRef, raw: dict[str, Any]) -> MarkdownSourceDocument | None:
        """Optional source document captured at load time. Base: none.

        MarkdownAdapter returns the markdown body + frontmatter for the
        annotation/anchor surface.
        """
        return None

    def on_owner_declared(
        self, *, entity: Entity, ref: SourceRef, raw: dict[str, Any], kind: str
    ) -> AggregateRowMeta | None:
        """Optional row-level triage metadata captured right after this entity's
        owner declaration is emitted. Base: none. AggregateAdapter returns one
        AggregateRowMeta per entities.yaml row (§B5).
        """
        return None

    def deferred_dataset_datapackage(
        self, *, entity: Entity, ref: SourceRef
    ) -> tuple[str, str] | None:
        """When this adapter defers (should_defer True), the (canonical_id, path)
        the loop should record in `dataset_datapackages`, or None to record
        nothing. Base: none. DatapackageAdapter returns its (id, path) so member
        resources stay locatable after the owner wins the column (§B4).
        """
        return None
