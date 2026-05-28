"""Offline ga4gh.vrs DataProxy backed by the local sequence store.

This proxy adapts local refget-digest sequence files for ga4gh.vrs translation
without fetching remote sequence data. Identifiers are normalized to bare
refget digests, and all sequence and metadata reads are served from the
provided :class:`~science_tool.commons.sequence_store.SequenceStore`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from science_tool.commons.sequence_store import SequenceStore


def _bare(identifier: str) -> str:
    return identifier.removeprefix("ga4gh:")


@dataclass
class RefgetProxy:
    store: SequenceStore

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        return self.store.sequence(_bare(identifier), start, end)

    def get_metadata(self, identifier: str) -> dict[str, Any]:
        digest = _bare(identifier)
        length = self.store.length(digest)
        return {"length": length, "aliases": [f"ga4gh:{digest}"], "alphabet": "ACGT", "added": None}

    def derive_refget_accession(self, identifier: str) -> str:
        digest = _bare(identifier)
        self.store.length(digest)
        return digest
