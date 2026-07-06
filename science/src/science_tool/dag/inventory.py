from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_model.contracts.inventory_common import (
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventoryWarning,
)


@dataclass(frozen=True)
class DagInventoryRecords:
    graph_addresses: list[InventoryGraphAddress] = field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = field(default_factory=list)
    warnings: list[InventoryWarning] = field(default_factory=list)


def load_dag_inventory_records(project_root: Path) -> DagInventoryRecords:
    """Return no standalone DAG graph-address records.

    DAG semantic edges are compiled propositions and are already represented in
    entity inventory.
    """
    return DagInventoryRecords()
