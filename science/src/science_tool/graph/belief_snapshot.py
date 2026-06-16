"""Append-only belief snapshots (design §4, Phase 2)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rdflib import RDF, URIRef

from .belief import collect_evidence_units
from .belief_policy import DEFAULT_BELIEF_POLICY
from .belief_scalar import belief_scalar, belief_scalar_enabled
from .belief_weights import CONFIG_VERSION
from .bundle_belief import BundleBeliefResult, belief_for_entity
from .io import SCI_NS, project_root_from_graph_path
from .store import _evidence_targets_for_uri, _graph_uri, _load_dataset


def _line_content_hash(knowledge, provenance, line: URIRef) -> str:
    parts: list[str] = []
    for graph in (knowledge, provenance):
        for _, predicate, obj in graph.triples((line, None, None)):
            parts.append(f"{predicate}\t{obj}")
    digest = hashlib.sha256("\n".join(sorted(parts)).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _claim_uris(knowledge):
    seen: set[URIRef] = set()
    for ctype in (SCI_NS.Proposition, SCI_NS.Hypothesis, SCI_NS.Mechanism):
        for subj, _, _ in knowledge.triples((None, RDF.type, ctype)):
            if isinstance(subj, URIRef) and subj not in seen:
                seen.add(subj)
                yield subj


def snapshot_records(knowledge, provenance, *, scalar_enabled: bool, as_of: str) -> list[dict]:
    rows: list[dict] = []
    for claim in _claim_uris(knowledge):
        result = belief_for_entity(knowledge, provenance, claim, scalar_enabled=scalar_enabled)

        if isinstance(result, BundleBeliefResult):
            member_uris = [URIRef(m.member_uri) for m in result.member_results]
            scalar = result.scalar
            # Reproducibility key (_key() requires input_hashes + scalar_enabled):
            # hashes of every member evidence-line input, PLUS a synthetic hash of
            # (composition_rule, sorted member ids) so a membership or rule change yields
            # a new snapshot row even when no underlying evidence line changed.
            member_units = collect_evidence_units(knowledge, provenance, member_uris)
            line_hashes = {_line_content_hash(knowledge, provenance, URIRef(u.line_uri)) for u in member_units}
            structure = "\n".join([result.composition_rule, *sorted(str(u) for u in member_uris)])
            structure_hash = "sha256:" + hashlib.sha256(structure.encode("utf-8")).hexdigest()
            input_hashes = sorted(line_hashes | {structure_hash})
            rows.append({
                "as_of": as_of,
                "claim": str(claim),
                "is_bundle": True,
                "composition_rule": result.composition_rule,
                "belief_state": result.magnitude.value,
                "capped_by_refutation": result.capped_by_refutation,
                "contested": result.contested,
                "bottleneck_members": result.bottleneck_members,
                "scalar_driver_member": (result.member_results[0].member_uri if result.member_results else None),
                "contested_members": result.contested_members,
                "unresolved_members": result.unresolved_members,
                "member_count": len(member_uris),
                "scalar_enabled": scalar_enabled,
                "net_band": list(scalar.net_band) if (scalar_enabled and scalar) else None,
                "net_robust": scalar.net_robust if (scalar_enabled and scalar) else None,
                "input_hashes": input_hashes,
                "config_version": CONFIG_VERSION,
                "policy_id": result.policy_id,
                "policy_version": result.policy_version,
            })
            continue

        # Plain proposition (or undecomposed-hypothesis fallback).
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        if not units:
            continue                                  # nothing to reproduce; skip
        scalar = belief_scalar(result)
        input_hashes = sorted({_line_content_hash(knowledge, provenance, URIRef(u.line_uri)) for u in units})
        rows.append({
            "as_of": as_of,
            "claim": str(claim),
            "is_bundle": False,
            "belief_state": result.magnitude.value,
            "contested": result.contested,
            "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
            "scalar_enabled": scalar_enabled,
            "massed_support_score": scalar.massed_support_score if scalar_enabled else None,
            "massed_dispute_score": scalar.massed_dispute_score if scalar_enabled else None,
            "massed_support_band": list(scalar.massed_support_band) if scalar_enabled else None,
            "massed_dispute_band": list(scalar.massed_dispute_band) if scalar_enabled else None,
            "net_band": list(scalar.net_band) if scalar_enabled else None,
            "net_robust": scalar.net_robust if scalar_enabled else None,
            "input_hashes": input_hashes,
            "config_version": CONFIG_VERSION,
            "policy_id": result.policy_id,
            "policy_version": result.policy_version,
        })
    rows.sort(key=lambda r: r["claim"])
    return rows


def make_snapshots(graph_path: Path, *, as_of: str) -> list[dict]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))
    return snapshot_records(knowledge, provenance, scalar_enabled=enabled, as_of=as_of)


def _key(row: dict):
    return (row["as_of"], row["claim"], tuple(row["input_hashes"]),
            row["config_version"], row["scalar_enabled"],
            row["policy_id"], row["policy_version"])


def _with_policy_defaults(row: dict) -> dict:
    # Pre-policy snapshot rows predate Spec 5 Slice A; they were computed by the
    # core-default policy. Stamp that identity explicitly so dedup and reproducibility
    # checks are policy-aware without rejecting or KeyError-ing on legacy history.
    if "policy_id" not in row:
        row["policy_id"] = DEFAULT_BELIEF_POLICY.policy_id
        row["policy_version"] = DEFAULT_BELIEF_POLICY.version
    return row


def _dump(row: dict) -> str:
    return json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def read_snapshots(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [
        _with_policy_defaults(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_snapshots(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = {_key(r) for r in read_snapshots(path)}
    added = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            if _key(row) in seen:
                continue
            handle.write(_dump(row) + "\n")
            seen.add(_key(row))
            added += 1
    return added
