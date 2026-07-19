from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from science_tool.archive import ArchiveRow
from science_tool.plan_common import ArchiveSelection, PathTransition


class PlannedArchiveRow(ArchiveRow):
    # The canonical ArchiveRow tolerates unknown keys (it parses append-only index files that may
    # carry future fields); a frozen plan is untrusted, so tighten to extra="forbid" here.
    model_config = ConfigDict(extra="forbid")


class ArchiveCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str | None
    status: str | None
    original_path: str | None
    superseded_by: str | None
    resynthesized_into: list[str]
    inbound_live_refs: list[str]


class ArchivePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[ArchiveCandidate]


class ArchiveMove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    original_path: str
    archive_path: str
    row: PlannedArchiveRow


class ArchivePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    op: Literal["archive"]
    now: str
    selection: ArchiveSelection
    moves: list[ArchiveMove]
    index: PathTransition | None = None  # None for an empty cohort (a no-op plan; legacy archive no-ops too)
    transitions: list[PathTransition]
    preview_report: ArchivePreviewReport

    @model_validator(mode="after")
    def _index_matches_moves(self) -> ArchivePlan:
        # I5: the moves↔index relationship is a schema invariant, not just an apply-time check. A
        # non-empty cohort MUST carry an index; an empty cohort MUST carry neither an index nor any
        # transition. This makes a malformed plan unconstructable rather than merely refused later.
        if self.moves and self.index is None:
            raise ValueError("a non-empty cohort must carry an archive-index transition")
        if not self.moves and (self.index is not None or self.transitions):
            raise ValueError("an empty cohort must carry no index and no transitions")
        return self
