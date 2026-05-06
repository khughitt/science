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


class StorageAdapter(ABC):
    """Abstract base class all storage adapters inherit from.

    Subclasses MUST override `discover()` and `load_raw()`. `dump()` is
    optional during migration; the default raises NotImplementedError.
    """

    name: str  # human-readable adapter name; travels in SourceRef.adapter_name

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
