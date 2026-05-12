from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from science_model.contracts.inventory_v1 import (
    InventoryFindingCandidate,
    InventoryGraphAddress,
    InventorySourceLocation,
    InventoryWarning,
)


@dataclass(frozen=True)
class DagInventoryRecords:
    graph_addresses: list[InventoryGraphAddress] = field(default_factory=list)
    finding_candidates: list[InventoryFindingCandidate] = field(default_factory=list)
    warnings: list[InventoryWarning] = field(default_factory=list)


def load_dag_inventory_records(project_root: Path) -> DagInventoryRecords:
    graph_addresses: list[InventoryGraphAddress] = []
    finding_candidates: list[InventoryFindingCandidate] = []
    warnings: list[InventoryWarning] = []

    for path in sorted((project_root / "doc" / "figures" / "dags").glob("*.edges.yaml")):
        rel_path = path.relative_to(project_root).as_posix()
        dag_slug = path.name.removesuffix(".edges.yaml")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        edges = payload.get("edges") or []
        seen_ids: set[str] = set()
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            edge_id = edge.get("id")
            if not isinstance(edge_id, str) or not edge_id:
                warnings.append(
                    InventoryWarning(
                        code="missing-dag-edge-id",
                        severity="warning",
                        message="DAG edge is missing a stable declared id.",
                        path=rel_path,
                    )
                )
                continue
            if edge_id in seen_ids:
                warnings.append(
                    InventoryWarning(
                        code="duplicate-dag-edge-id",
                        severity="warning",
                        message=f"DAG edge id {edge_id!r} appears more than once in this DAG.",
                        path=rel_path,
                    )
                )
                continue
            seen_ids.add(edge_id)
            address = f"dag-edge:{dag_slug}:{edge_id}"
            source = InventorySourceLocation(adapter="dag", path=rel_path, address=edge_id)
            graph_addresses.append(
                InventoryGraphAddress(
                    address=address,
                    kind="dag-edge",
                    label=_edge_label(edge),
                    source=source,
                )
            )
            interpretation = edge.get("interpretation") or edge.get("finding") or edge.get("claim")
            if isinstance(interpretation, str) and interpretation.strip():
                finding_candidates.append(
                    InventoryFindingCandidate(
                        candidate_id=f"finding-candidate:{address}",
                        title=interpretation.strip(),
                        targets=[address],
                        source=source,
                        reason="DAG edge contains claim-bearing interpretation text.",
                    )
                )

    return DagInventoryRecords(
        graph_addresses=graph_addresses,
        finding_candidates=finding_candidates,
        warnings=warnings,
    )


def _edge_label(edge: dict[str, Any]) -> str:
    source = str(edge.get("source") or "")
    relation = str(edge.get("relation") or "edge")
    target = str(edge.get("target") or "")
    return " ".join(part for part in (source, relation, target) if part)
