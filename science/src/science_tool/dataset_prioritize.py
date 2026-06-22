"""Pure scoring core for `science dataset prioritize`.

score(d) = readiness_weight(d) × (1 + reach(d)) × leverage_tilt(d)

Design: docs/plans/2026-06-21-catalog-datasets-design.md.
Readiness reuses the canonical DatasetEntity.readiness(); leverage reuses the
computed _claim_summary_data signals; reach merges a frontmatter path (no graph
needed) with a graph dataset_usage path.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import RDF

from science_model.entities import DatasetEntity, Readiness
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.store.constants import CITO_NS, SCI_NS
from science_tool.graph.store.identity import canonical_id_from_entity_uri
from science_tool.graph.store.summary import _claim_summary_data
from science_model.frontmatter import parse_frontmatter
from science_tool.datasets_catalog import _local_rows

# Base Entity fields that a normal on-disk dataset frontmatter omits but
# DatasetEntity.model_validate requires. Backfilled so we can call the canonical
# .readiness() instead of re-interpreting access state.
_BASE_BACKFILL = {
    "kind": "dataset",
    "project": "_prioritize",
    "source_refs": [],
    "content_preview": "",
    "file_path": "doc/datasets/_.md",
}


def readiness_for(fm: dict) -> Readiness:
    """Canonical readiness for an on-disk dataset frontmatter dict.

    Returns Readiness(ready=False, state="unknown") if the entity cannot be
    constructed (malformed frontmatter) — the caller flags that as unresolved.
    """
    payload = {
        "ontology_terms": fm.get("ontology_terms") or [],
        "related": fm.get("related") or [],
        **fm,
        **_BASE_BACKFILL,
    }
    try:
        return DatasetEntity.model_validate(payload).readiness()
    except Exception:
        return Readiness(ready=False, state="unknown", detail="unparseable dataset entity")


# Exact readiness.state strings → weight. Ordering is load-bearing; constants tunable.
_STATE_WEIGHT: dict[str, float] = {
    "available": 1.0,
    "derived-via-code": 0.6,
    "derived-via-member-of": 0.6,
    "derived-via-workflow-recipe": 0.6,
    "consumable-via-scope-reduced": 0.55,
    "consumable-via-substituted": 0.55,
    "acquiring": 0.4,
    "embargoed": 0.05,
    "withdrawn": 0.05,
}
_UNVERIFIED_LEVEL_WEIGHT: dict[str, float] = {
    "public": 0.7,
    "registration": 0.5,
    "mixed": 0.5,
    "controlled": 0.3,
    "commercial": 0.3,
}
_UNRESOLVED_WEIGHT = 0.1


def readiness_weight(fm: dict) -> tuple[float, list[str]]:
    """(weight, flags) for a dataset frontmatter. Unrecognized state → flagged default."""
    state = readiness_for(fm).state
    if state in _STATE_WEIGHT:
        return _STATE_WEIGHT[state], []
    if state.endswith(", unverified"):
        level = state[: -len(", unverified")]
        return _UNVERIFIED_LEVEL_WEIGHT.get(level, _UNRESOLVED_WEIGHT), []
    return _UNRESOLVED_WEIGHT, ["readiness-unresolved"]


_QH_PREFIXES = ("question:", "hypothesis:")


def _is_qh(ref: str) -> bool:
    return isinstance(ref, str) and ref.startswith(_QH_PREFIXES)


# Roots that hold the entities reach cares about, mirroring load_project_sources
# (graph/sources.py:305): the 21 entity-layout kinds (questions, hypotheses,
# propositions, evidence-lines, ...) live under entities/; datasets stay at
# doc/datasets/. Scan both — NOT a bare doc/ scan (Q/H are NOT under doc/).
_REACH_SCAN_ROOTS = ("entities", "doc/datasets")


def _iter_entity_frontmatter(project_root: Path):
    """Yield (id, fm) for every markdown entity under the reach scan roots.

    Files without an id are skipped.
    """
    for root in _REACH_SCAN_ROOTS:
        base = project_root / root
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            parsed = parse_frontmatter(md)
            if parsed is None:
                continue
            fm, _ = parsed
            ent_id = fm.get("id")
            if isinstance(ent_id, str) and ent_id:
                yield ent_id, fm


def frontmatter_reach(project_root: Path) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {}
    # Collect dataset ids and the Q/H ids; build both directions.
    for ent_id, fm in _iter_entity_frontmatter(project_root):
        kind = (fm.get("kind") or fm.get("type") or "")
        related = [r for r in (fm.get("related") or []) if isinstance(r, str)]
        if kind == "dataset":
            reach.setdefault(ent_id, set())
            reach[ent_id].update(r for r in related if _is_qh(r))
        elif _is_qh(ent_id):
            # back-edge: a Q/H listing dataset:x in its own related
            for r in related:
                if isinstance(r, str) and r.startswith("dataset:"):
                    reach.setdefault(r, set()).add(ent_id)
    return reach


def _qh_for_proposition(knowledge, prop_uri: URIRef) -> set[URIRef]:
    """Hypotheses (prop discusses) + questions (question addresses prop)."""
    out: set[URIRef] = set()
    for _, _, hyp in knowledge.triples((prop_uri, CITO_NS.discusses, None)):
        if isinstance(hyp, URIRef) and (hyp, RDF.type, SCI_NS.Hypothesis) in knowledge:
            out.add(hyp)
    for q in knowledge.subjects(SCI_NS.addresses, prop_uri):
        if isinstance(q, URIRef) and (q, RDF.type, SCI_NS.Question) in knowledge:
            out.add(q)
    return out


def merged_reach(
    project_root: Path,
    knowledge=None,
    provenance=None,
    dataset_ids: list[str] | None = None,
) -> dict[str, set[str]]:
    fm_reach = frontmatter_reach(project_root)
    ids = dataset_ids if dataset_ids is not None else sorted(fm_reach)
    merged: dict[str, set[str]] = {ds_id: set(fm_reach.get(ds_id, set())) for ds_id in ids}
    if knowledge is not None and provenance is not None:
        for ds_id, targets in usage_reach(knowledge, provenance, ids).items():
            merged.setdefault(ds_id, set()).update(targets)  # union dedups by target id
    return merged


# leverage contribution per signal/field, summed across reached propositions then capped.
_LEVERAGE_PER_SIGNAL = {"contested": 0.4, "single_source": 0.3, "no_empirical_data": 0.2}
_LEVERAGE_RISK_SCALE = 0.05  # × risk_score, modest
_LEVERAGE_CAP = 2.0


def reached_proposition_uris(knowledge, provenance, dataset_id: str) -> set[URIRef]:
    """Propositions a dataset reaches via the usage path (URIs, for signal lookup)."""
    props: set[URIRef] = set()
    ds_uri = project_entity_uri(dataset_id)
    for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
        for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
            for _, _, prop in knowledge.triples((consumer, CITO_NS.supports, None)):
                if isinstance(prop, URIRef):
                    props.add(prop)
            for _, _, prop in knowledge.triples((consumer, CITO_NS.disputes, None)):
                if isinstance(prop, URIRef):
                    props.add(prop)
    return props


def leverage_tilt(knowledge, provenance, dataset_id: str, *, usage_props=None) -> float:
    props = usage_props if usage_props is not None else reached_proposition_uris(
        knowledge, provenance, dataset_id
    )
    if not props:
        return 1.0
    bonus = 0.0
    for prop in props:
        summary = _claim_summary_data(knowledge, provenance, prop)
        if summary is None:
            continue
        for sig in summary.get("signals", []):
            bonus += _LEVERAGE_PER_SIGNAL.get(sig, 0.0)
        bonus += _LEVERAGE_RISK_SCALE * float(summary.get("risk_score", 0.0))
    return min(_LEVERAGE_CAP, 1.0 + bonus)


def usage_reach(knowledge, provenance, dataset_ids: list[str]) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {ds_id: set() for ds_id in dataset_ids}
    for ds_id in dataset_ids:
        ds_uri = project_entity_uri(ds_id)
        # usage nodes referencing this dataset, then their consumers (evidence-lines)
        for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
            for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
                # consumer (evidence-line) supports/disputes a proposition (knowledge graph)
                props: set[URIRef] = set()
                for _, _, prop in knowledge.triples((consumer, CITO_NS.supports, None)):
                    props.add(prop)
                for _, _, prop in knowledge.triples((consumer, CITO_NS.disputes, None)):
                    props.add(prop)
                for prop in props:
                    if not isinstance(prop, URIRef):
                        continue
                    for qh in _qh_for_proposition(knowledge, prop):
                        ref = canonical_id_from_entity_uri(str(qh))
                        if ref is not None:  # skip non-entity URIs
                            reach[ds_id].add(ref)
    return reach


def _gap_flags_for(row_fm: dict, reach_n: int, readiness_flags: list[str]) -> list[str]:
    flags = list(readiness_flags)
    if reach_n == 0:
        flags.append("no-edge")
    origin = row_fm.get("origin")
    access = row_fm.get("access") or {}
    verified = bool(access.get("verified")) if isinstance(access, dict) else False
    if origin == "external" and not verified:
        flags.append("unverified")
    return flags


def _top_reason(weight: float, readiness_state: str, reach_n: int, tilt: float) -> str:
    bits = [f"readiness={readiness_state}({weight:g})", f"reach={reach_n}"]
    if tilt > 1.0:
        bits.append(f"leverage×{tilt:g}")
    return ", ".join(bits)


def prioritize(
    project_root: Path,
    *,
    knowledge=None,
    provenance=None,
    origin: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    level: str | None = None,
) -> list[dict]:
    """Return dataset rows sorted by score desc (tie-break by id).

    score = readiness_weight × (1 + reach) × leverage_tilt

    Each row: {id, title, score, readiness, reach, top_reason, gap_flags}.
    leverage_tilt is only applied when both knowledge and provenance are provided;
    otherwise tilt = 1.0.
    """
    rows_in = _local_rows(project_root)
    dataset_ids = [r["id"] for r in rows_in]
    reach_map = merged_reach(project_root, knowledge, provenance, dataset_ids)

    out: list[dict] = []
    for r in rows_in:
        if origin is not None and r["origin"] != origin:
            continue
        if status is not None and r["status"] != status:
            continue
        if tier is not None and r["tier"] != tier:
            continue
        if level is not None and r["level"] != level:
            continue
        slug = r["id"].split(":", 1)[-1]
        parsed = parse_frontmatter(project_root / "doc" / "datasets" / f"{slug}.md")
        fm = parsed[0] if parsed else {}
        weight, r_flags = readiness_weight(fm)
        reach_set = reach_map.get(r["id"], set())
        reach_n = len(reach_set)
        tilt = 1.0
        if knowledge is not None and provenance is not None:
            tilt = leverage_tilt(knowledge, provenance, r["id"])
        score = weight * (1 + reach_n) * tilt
        out.append({
            "id": r["id"],
            "title": r["title"],
            "score": round(score, 4),
            "readiness": readiness_for(fm).state,
            "reach": reach_n,
            "top_reason": _top_reason(weight, readiness_for(fm).state, reach_n, tilt),
            "gap_flags": _gap_flags_for(fm, reach_n, r_flags),
        })
    out.sort(key=lambda d: (-d["score"], d["id"]))
    return out
