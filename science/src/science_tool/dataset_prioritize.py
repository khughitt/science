"""Pure scoring core for `science dataset prioritize`.

score(d) = readiness_weight(d) × (1 + reach(d)) × leverage_tilt(d)

Readiness reuses the canonical DatasetEntity.readiness(); leverage reuses the
computed _claim_summary_data signals; reach merges a frontmatter path (no graph
needed) with a graph dataset_usage path. See docs/user-guide/entities.md.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import URIRef
from rdflib.namespace import RDF, SKOS

from science_model.entities import DatasetEntity, Readiness
from science_tool.datasets.semantics import DatasetClass, RuntimeState, dataset_class_for, runtime_state_for
from science_tool.graph.dataset_usage import project_entity_uri
from science_tool.graph.store.constants import CITO_NS, SCI_NS
from science_tool.graph.store.identity import canonical_id_from_entity_uri
from science_tool.graph.store.summary import _claim_summary_data
from science_model.frontmatter import parse_frontmatter
from science_tool.datasets.capabilities import capability_fit
from science_tool.datasets_catalog import GATED_LEVELS, _local_rows
from science_tool.entity_scan import iter_entity_markdown

# Base Entity fields that a normal on-disk dataset frontmatter omits but
# DatasetEntity.model_validate requires. Backfilled so we can call the canonical
# .readiness() instead of re-interpreting access state.
_BASE_BACKFILL = {
    "kind": "dataset",
    "project": "_prioritize",
    "source_refs": [],
    "content_preview": "",
    "file_path": "entities/datasets/_.md",
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


def _dataset_usage_refs(fm: dict) -> list[str]:
    usage = fm.get("dataset_usage") or []
    if not isinstance(usage, list):
        return []
    refs: list[str] = []
    for entry in usage:
        if not isinstance(entry, dict):
            continue
        ref = entry.get("ref")
        if isinstance(ref, str) and ref.startswith("dataset:"):
            refs.append(ref)
    return refs


def _iter_entity_frontmatter(project_root: Path):
    """Yield (id, fm) for every live markdown entity under entities/.

    Every entity-layout kind reach cares about — questions, hypotheses,
    propositions, evidence-lines, AND datasets — lives under entities/ post-migration.
    Routed through the sanctioned ``iter_entity_markdown`` scanner so the ``_archive``
    skip stays authoritative (enforced by the entity-scan guard test). Files without
    an id are skipped.
    """
    for md in iter_entity_markdown(project_root / "entities"):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        ent_id = fm.get("id")
        if isinstance(ent_id, str) and ent_id:
            yield ent_id, fm


def frontmatter_reach(project_root: Path) -> dict[str, set[str]]:
    reach: dict[str, set[str]] = {}
    # Collect dataset ids and the Q/H ids; build every source-authored direction.
    for ent_id, fm in _iter_entity_frontmatter(project_root):
        kind = fm.get("kind") or fm.get("type") or ""
        related = [r for r in (fm.get("related") or []) if isinstance(r, str)]
        if kind == "dataset":
            reach.setdefault(ent_id, set())
            reach[ent_id].update(r for r in related if _is_qh(r))
        elif _is_qh(ent_id):
            # back-edge: a Q/H listing dataset:x in its own related
            for r in related:
                if isinstance(r, str) and r.startswith("dataset:"):
                    reach.setdefault(r, set()).add(ent_id)
            # first-class Q/H surface: datasets: ["dataset:x", ...]
            datasets = [r for r in (fm.get("datasets") or []) if isinstance(r, str)]
            for dataset_id in datasets:
                if dataset_id.startswith("dataset:"):
                    reach.setdefault(dataset_id, set()).add(ent_id)

        # General source-authored usage bridge: papers are the motivating case,
        # but any entity carrying dataset_usage and related Q/H records the same
        # dataset-inquiry fact.
        qh_targets = {r for r in related if _is_qh(r)}
        if qh_targets:
            for dataset_ref in _dataset_usage_refs(fm):
                reach.setdefault(dataset_ref, set()).update(qh_targets)
    return reach


def _qh_for_proposition(knowledge, prop_uri: URIRef) -> set[URIRef]:
    """Questions/hypotheses a proposition reaches, as the UNION of three sources:

    1. direct ``prop cito:discusses hypothesis``,
    2. direct ``question sci:addresses prop`` (traversed backward),
    3. the materialized transitive ``sci:bearsOn`` closure targets typed
       Question/Hypothesis (graph/freshness.py ``close_bears_on``) — catches a
       Q/H reachable only via a multi-hop chain, e.g. ``P cito:supports P2
       cito:supports H`` yields ``P bearsOn H`` at depth 2.

    Union, NOT replacement: ``cito:discusses``/``sci:addresses`` are not bearsOn
    deriver rules, so the closure alone would drop sources 1-2. Purely additive —
    can only add Q/H, never remove.
    """
    out: set[URIRef] = set()
    for _, _, hyp in knowledge.triples((prop_uri, CITO_NS.discusses, None)):
        if isinstance(hyp, URIRef) and (hyp, RDF.type, SCI_NS.Hypothesis) in knowledge:
            out.add(hyp)
    for q in knowledge.subjects(SCI_NS.addresses, prop_uri):
        if isinstance(q, URIRef) and (q, RDF.type, SCI_NS.Question) in knowledge:
            out.add(q)
    for tgt in knowledge.objects(prop_uri, SCI_NS.bearsOn):
        if not isinstance(tgt, URIRef):
            continue
        if (tgt, RDF.type, SCI_NS.Hypothesis) in knowledge or (tgt, RDF.type, SCI_NS.Question) in knowledge:
            out.add(tgt)
    return out


def _qh_for_consumer_related(knowledge, consumer: URIRef) -> set[URIRef]:
    out: set[URIRef] = set()
    for target in knowledge.objects(consumer, SKOS.related):
        if not isinstance(target, URIRef):
            continue
        if (target, RDF.type, SCI_NS.Hypothesis) in knowledge or (target, RDF.type, SCI_NS.Question) in knowledge:
            out.add(target)
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
    props = usage_props if usage_props is not None else reached_proposition_uris(knowledge, provenance, dataset_id)
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
        # usage nodes referencing this dataset, then their consumers
        for usage_node in provenance.subjects(SCI_NS.dataset, ds_uri):
            for consumer in provenance.subjects(SCI_NS.hasDatasetUsage, usage_node):
                # consumer (usually evidence-line) supports/disputes a proposition
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
                for qh in _qh_for_consumer_related(knowledge, consumer):
                    ref = canonical_id_from_entity_uri(str(qh))
                    if ref is not None:
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


def _dataset_path(project_root: Path, dataset_id: str) -> Path:
    slug = dataset_id.split(":", 1)[-1]
    return project_root / "entities" / "datasets" / f"{slug}.md"


def _frontmatter_for_row(project_root: Path, row: dict) -> dict:
    parsed = parse_frontmatter(_dataset_path(project_root, row["id"]))
    return parsed[0] if parsed else {}


def _access_info(fm: dict) -> tuple[str, bool, bool]:
    access = fm.get("access") or {}
    if not isinstance(access, dict):
        return "", False, False
    exception = access.get("exception") or {}
    has_exception = isinstance(exception, dict) and bool(exception.get("mode"))
    return str(access.get("level") or ""), access.get("verified") is True, has_exception


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
    include_gated: bool = False,
    include_reference: bool = False,
    include_pointer: bool = False,
    runtime_state: RuntimeState | None = None,
) -> list[dict]:
    """Return dataset rows sorted by score desc (tie-break by id).

    score = readiness_weight × (1 + reach) × leverage_tilt

    Each row: {id, title, score, readiness, reach, reaches, top_reason, gap_flags}.
    leverage_tilt is only applied when both knowledge and provenance are provided;
    otherwise tilt = 1.0.

    Gated deposits, references, and pointers are excluded by default so the
    ranking stays actionable. Explicit include flags, explicit --level, or an
    explicit runtime-state filter surface those rows.
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
        fm = _frontmatter_for_row(project_root, r)
        try:
            dataset_class: DatasetClass = dataset_class_for(fm)
            row_runtime_state: RuntimeState = runtime_state_for(fm)
        except ValueError:
            dataset_class = "deposit"
            row_runtime_state = "blocked-access"
        if runtime_state is not None and row_runtime_state != runtime_state:
            continue
        if runtime_state is None:
            if not include_gated and level is None and dataset_class == "deposit" and r["level"] in GATED_LEVELS:
                # Non-gated by default; an explicit --level overrides this exclusion.
                continue
            if dataset_class == "reference" and not include_reference:
                continue
            if dataset_class == "pointer" and not include_pointer:
                continue
        access_level, access_verified, access_exception = _access_info(fm)
        weight, r_flags = readiness_weight(fm)
        reach_set = reach_map.get(r["id"], set())
        reach_n = len(reach_set)
        tilt = 1.0
        if knowledge is not None and provenance is not None:
            tilt = leverage_tilt(knowledge, provenance, r["id"])
        score = weight * (1 + reach_n) * tilt
        out.append(
            {
                "id": r["id"],
                "title": r["title"],
                "score": round(score, 4),
                "readiness": readiness_for(fm).state,
                "reach": reach_n,
                "reaches": sorted(reach_set),
                "top_reason": _top_reason(weight, readiness_for(fm).state, reach_n, tilt),
                "gap_flags": _gap_flags_for(fm, reach_n, r_flags),
                "dataset_class": dataset_class,
                "runtime_state": row_runtime_state,
                "access_level": access_level,
                "access_verified": access_verified,
                "access_exception": access_exception,
            }
        )
    out.sort(key=lambda d: (-d["score"], d["id"]))
    return out


def excluded_summary(
    project_root: Path,
    *,
    origin: str | None = None,
    status: str | None = None,
    tier: str | None = None,
    level: str | None = None,
    include_gated: bool = False,
    include_reference: bool = False,
    include_pointer: bool = False,
    runtime_state: RuntimeState | None = None,
) -> dict[str, int]:
    """Count rows hidden by the default actionable ranking."""
    summary = {"gated": 0, "reference": 0, "pointer": 0}
    if runtime_state is not None:
        return summary
    for row in _local_rows(project_root):
        if origin is not None and row["origin"] != origin:
            continue
        if status is not None and row["status"] != status:
            continue
        if tier is not None and row["tier"] != tier:
            continue
        if level is not None and row["level"] != level:
            continue
        fm = _frontmatter_for_row(project_root, row)
        try:
            dataset_class = dataset_class_for(fm)
        except ValueError:
            dataset_class = "deposit"
        if dataset_class == "reference":
            if not include_reference:
                summary["reference"] += 1
            continue
        if dataset_class == "pointer":
            if not include_pointer:
                summary["pointer"] += 1
            continue
        if not include_gated and level is None and row["level"] in GATED_LEVELS:
            summary["gated"] += 1
    return summary


def _coverage_state_and_reason(counts: dict[str, int]) -> tuple[str, str]:
    if counts["runnable"] > 0:
        return "covered-runnable", "none"
    if counts["unstaged_deposit"] > 0:
        return "covered-unstaged", "unstaged-deposit"
    if counts["reference"] > 0:
        return "covered-reference", "only-reference"
    if counts["pointer"] > 0:
        return "covered-pointer", "only-pointer"
    if counts["gated"] > 0:
        return "blocked-access", "only-gated"
    if counts["unverified"] > 0:
        return "unverified", "only-unverified"
    return "no-candidate", "no-candidate"


def _capability_gap_reason(incompatible_datasets: list[dict[str, object]]) -> str:
    reasons = {str(row["reason"]) for row in incompatible_datasets}
    if reasons == {"missing-required-capabilities"}:
        return "missing-required-capabilities"
    if reasons == {"missing-provided-capabilities"}:
        return "missing-provided-capabilities"
    if "capability-mismatch" in reasons:
        return "capability-mismatch"
    if "missing-provided-capabilities" in reasons:
        return "missing-provided-capabilities"
    return "missing-required-capabilities"


def target_coverage(rows: list[dict], project_root: Path) -> list[dict]:
    """Invert prioritized dataset rows into per-question/hypothesis coverage rows."""
    targets: dict[str, dict[str, object]] = {}
    for ent_id, fm in _iter_entity_frontmatter(project_root):
        if not _is_qh(ent_id):
            continue
        targets[ent_id] = {
            "target": ent_id,
            "title": fm.get("title", ""),
            "frontmatter": fm,
            "datasets": [],
            "dataset_count": 0,
            "compatible_datasets": [],
            "compatible_dataset_count": 0,
            "incompatible_datasets": [],
            "coverage_state": "no-candidate",
            "gap_reason": "no-candidate",
            "counts": {
                "runnable": 0,
                "unstaged_deposit": 0,
                "reference": 0,
                "pointer": 0,
                "unverified": 0,
                "gated": 0,
            },
        }

    by_target: dict[str, list[dict]] = {target: [] for target in targets}
    for row in rows:
        for target in row.get("reaches", []):
            if target in by_target:
                by_target[target].append(row)

    for target, target_rows in by_target.items():
        datasets = sorted(row["id"] for row in target_rows)
        target_fm = targets[target]["frontmatter"]
        compatible_rows: list[dict] = []
        incompatible_datasets: list[dict[str, object]] = []
        for row in target_rows:
            dataset_fm = _frontmatter_for_row(project_root, row)
            fit = capability_fit(
                target_fm.get("required_capabilities") if isinstance(target_fm, dict) else None,
                dataset_fm.get("provided_capabilities"),
            )
            if fit.compatible:
                compatible_rows.append(row)
                continue
            incompatible_datasets.append(
                {
                    "dataset": row["id"],
                    "reason": fit.reason,
                    "required_capabilities": fit.required,
                    "provided_capabilities": fit.provided,
                }
            )
        counts = {
            "runnable": 0,
            "unstaged_deposit": 0,
            "reference": 0,
            "pointer": 0,
            "unverified": 0,
            "gated": 0,
        }
        for row in compatible_rows:
            runtime = row.get("runtime_state")
            if runtime == "runnable":
                counts["runnable"] += 1
            elif runtime == "unstaged-deposit":
                counts["unstaged_deposit"] += 1
            elif runtime == "reference-only":
                counts["reference"] += 1
            elif runtime == "pointer-only":
                counts["pointer"] += 1
            elif runtime == "blocked-access":
                if row.get("access_exception") or row.get("access_level") in GATED_LEVELS:
                    counts["gated"] += 1
                else:
                    counts["unverified"] += 1
        if compatible_rows:
            coverage_state, gap_reason = _coverage_state_and_reason(counts)
        elif target_rows:
            gap_reason = _capability_gap_reason(incompatible_datasets)
            coverage_state = gap_reason
        else:
            coverage_state, gap_reason = _coverage_state_and_reason(counts)
        targets[target]["datasets"] = datasets
        targets[target]["dataset_count"] = len(datasets)
        targets[target]["compatible_datasets"] = sorted(row["id"] for row in compatible_rows)
        targets[target]["compatible_dataset_count"] = len(compatible_rows)
        targets[target]["incompatible_datasets"] = sorted(incompatible_datasets, key=lambda row: str(row["dataset"]))
        targets[target]["coverage_state"] = coverage_state
        targets[target]["gap_reason"] = gap_reason
        targets[target]["counts"] = counts

    for target in targets.values():
        target.pop("frontmatter", None)
    return [targets[target] for target in sorted(targets)]
