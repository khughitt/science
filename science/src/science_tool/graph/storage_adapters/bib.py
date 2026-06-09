"""BibAdapter — the project bibliography (`papers/references.bib`) as an
external-reference authority (design §B2/§B3a/§C3, Phase 4b).

Synthesizes a lightweight `paper:<citekey>` raw record per balanced bib entry.
These are external references, not owners: the load loop tags their identity rows
ParticipationMode.EXTERNAL_REFERENCE (never renumbered, never a collision) and the
materializer emits a minimal metadata node so citation edges resolve. No `dump`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.bibliography import BibEntry, load_bib_entries
from science_tool.graph.identity_table import ParticipationMode
from science_tool.graph.storage_adapters.base import StorageAdapter

_BIB_REL = "papers/references.bib"


class BibAdapter(StorageAdapter):
    """Reads `papers/references.bib` into external-reference paper records."""

    name = "bib"
    participation_mode = ParticipationMode.EXTERNAL_REFERENCE

    def __init__(self) -> None:
        self._entries: dict[str, BibEntry] = {}
        self._keys_by_line: list[str] = []

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._entries = load_bib_entries(project_root)
        self._keys_by_line = list(self._entries)  # insertion order = bib file order
        return [SourceRef(adapter_name=self.name, path=_BIB_REL, line=i) for i in range(len(self._keys_by_line))]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        assert ref.line is not None, "BibAdapter SourceRef must carry line (entry index)"
        entry = self._entries[self._keys_by_line[ref.line]]
        raw: dict[str, Any] = {
            "kind": "paper",
            "id": f"paper:{entry.key}",
            "title": entry.title or entry.key,
            "bibkey": entry.key,
            "file_path": _BIB_REL,
        }
        if entry.year is not None:
            raw["year"] = entry.year
        if entry.doi:
            raw["doi"] = entry.doi
        if entry.url:
            raw["url"] = entry.url
        return raw
