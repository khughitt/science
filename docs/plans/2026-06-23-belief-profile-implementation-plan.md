# Belief Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `science belief profile`, a read-only derived per-entity epistemic profile over existing belief, evidence, cap, scalar, and freshness machinery.

**Architecture:** Add one focused graph module that computes deterministic profile rows from in-memory RDF graphs, then expose it through the existing `science belief` click group. The command does not materialize RDF, does not persist new metadata, and does not introduce a new belief engine; it reuses `belief_for_entity`, `aggregate_belief`, `BundleBeliefResult`, `belief_scalar`, evidence collection, and materialized freshness state.

**Tech Stack:** Python 3.12, click CLI, rdflib graphs, pytest, existing `science_tool.graph` modules.

---

## Scope

Implement the v1 design from `docs/plans/2026-06-23-belief-profile-design.md`.

In scope:

- `science belief profile --format json`
- `science belief profile --format table`
- `--kind proposition|hypothesis|mechanism`, repeatable with OR semantics
- `--label <label>`, repeatable with AND semantics and validated against the fixed v1 label set
- `--all` to include every supported belief-bearing entity
- supported entity kinds: `proposition`, `hypothesis`, `mechanism`
- categorical labels: `speculative`, `fragile`, `supported`, `well_supported`, `contested`, `single_source`, `no_empirical_data`, `authored_only`, `literature_only`, `empirical_data_backed`, `authored_capped`, `qa_dataset_capped`, `capped_by_refutation`, `stale`, `needs_review`
- `diagnostic_count: null` for bundle rows
- `freshness_state` values read exactly as `needs-review`, `stale`, `fresh`, or `null`
- `belief_scalar: null` when existing scalar feature is disabled; otherwise expose existing scalar fields
- default output includes resolved hypothesis/mechanism bundles with core member propositions even when those members are evidence-free; this follows the design's bundle-membership predicate and may be noisy

Out of scope:

- new RDF predicates
- authored `EpistemicMetadata`
- new scalar math
- labels that require normalized source-agent provenance, including `ai_drafted`, `human_ratified`, and `editorial_only`
- health/validation gates

## File Structure

- Modify `science/src/science_tool/graph/store/summary.py`
  - Promote the empirical-evidence classifier to `is_empirical_evidence_type()` so profile code can reuse the graph summary semantics without copying the type set.

- Create `science/src/science_tool/graph/belief_profile.py`
  - Owns profile row construction, label derivation, default inclusion, filtering, scalar projection, graph loading, and stable local entity refs.
  - Public API:
    - `SUPPORTED_KINDS`
    - `PROFILE_LABELS`
    - `profile_records(knowledge, provenance, *, scalar_enabled, include_all=False, kinds=(), labels=()) -> list[dict[str, Any]]`
    - `make_profiles(graph_path, *, include_all=False, kinds=(), labels=()) -> list[dict[str, Any]]`

- Modify `science/src/science_tool/cli.py`
  - Import `belief_profile`.
  - Add `science belief profile`.
  - Emit JSON/table through `emit_query_rows()`.

- Create `science/tests/test_belief_profile.py`
  - Unit tests for graph-level row construction, labels, bundle handling, filters, default inclusion, freshness, empirical type semantics, and scalar null behavior.

- Modify `science/tests/test_belief_cli.py`
  - Add a CLI test that verifies `belief profile` parses flags and emits the query-row JSON envelope.

- Modify `docs/plans/2026-06-23-belief-profile-design.md`
  - Mark the design as implementation-ready and point to this implementation plan.

## Task 1: Empirical Evidence Helper

**Files:**
- Modify: `science/src/science_tool/graph/store/summary.py`
- Test: `science/tests/test_belief_profile.py`

- [ ] **Step 1: Write the failing helper import test**

Create `science/tests/test_belief_profile.py` with this initial content:

```python
from science_tool.graph.store.summary import is_empirical_evidence_type


def test_profile_reuses_summary_empirical_type_semantics() -> None:
    assert is_empirical_evidence_type("empirical_data")
    assert is_empirical_evidence_type("empirical_data_evidence")
    assert is_empirical_evidence_type("benchmark")
    assert not is_empirical_evidence_type("literature")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py::test_profile_reuses_summary_empirical_type_semantics -q
```

Expected: FAIL with `ImportError: cannot import name 'is_empirical_evidence_type'`.

- [ ] **Step 3: Promote the helper**

In `science/src/science_tool/graph/store/summary.py`, replace the private helper and its caller:

```python
_EMPIRICAL_TYPES = frozenset({EvidenceType.EMPIRICAL_DATA, EvidenceType.BENCHMARK})


def is_empirical_evidence_type(evidence_type: str | None) -> bool:
    """True iff the evidence type literal normalizes to empirical-grade data."""
    return normalize_evidence_type(evidence_type) in _EMPIRICAL_TYPES
```

Then change `_claim_summary_data()` from:

```python
has_empirical_data = any(_is_empirical_type(evidence_type) for evidence_type in evidence_types)
```

to:

```python
has_empirical_data = any(is_empirical_evidence_type(evidence_type) for evidence_type in evidence_types)
```

- [ ] **Step 4: Run the helper test to verify it passes**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py::test_profile_reuses_summary_empirical_type_semantics -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/store/summary.py science/tests/test_belief_profile.py
rtk git commit -m "refactor: expose empirical evidence classifier"
```

## Task 2: Core Profile Rows

**Files:**
- Create: `science/src/science_tool/graph/belief_profile.py`
- Modify: `science/tests/test_belief_profile.py`

- [ ] **Step 1: Extend the graph-level tests**

Replace `science/tests/test_belief_profile.py` with:

```python
from __future__ import annotations

from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import PROV, SKOS

from science_tool.graph.belief import EVIDENCE_LINE_CLASS
from science_tool.graph.belief_profile import profile_records
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.store.summary import is_empirical_evidence_type


PROP_A = URIRef(PROJECT_NS["proposition/pa"])
PROP_B = URIRef(PROJECT_NS["proposition/pb"])
PROP_EMPTY = URIRef(PROJECT_NS["proposition/empty"])
HYP = URIRef(PROJECT_NS["hypothesis/h1"])


def _line(
    knowledge: Graph,
    provenance: Graph,
    target: URIRef,
    line_id: str,
    *,
    stance: str = "supports",
    evidence_type: str = "empirical_data",
    evidence_role: str = "direct_test",
    strength: str = "strong",
    independence: str = "independent",
    group: str | None = None,
    source: str | None = None,
    dispute_scope: str | None = None,
    confidence: float | None = None,
) -> URIRef:
    line = URIRef(PROJECT_NS[f"evidence-line/{line_id}"])
    knowledge.add((line, RDF.type, EVIDENCE_LINE_CLASS))
    predicate = CITO_NS.supports if stance == "supports" else CITO_NS.disputes
    knowledge.add((line, predicate, target))
    provenance.add((line, SCI_NS.evidenceType, Literal(evidence_type)))
    provenance.add((line, SCI_NS.evidenceRole, Literal(evidence_role)))
    provenance.add((line, SCI_NS.evidenceStrength, Literal(strength)))
    provenance.add((line, SCI_NS.evidenceIndependence, Literal(independence)))
    provenance.add((line, SCI_NS.independenceGroup, Literal(group or line_id)))
    if source is not None:
        provenance.add((line, PROV.wasDerivedFrom, URIRef(source)))
    if dispute_scope is not None:
        provenance.add((line, SCI_NS.disputeScope, Literal(dispute_scope)))
    if confidence is not None:
        provenance.add((line, SCI_NS.confidence, Literal(confidence)))
    return line


def _base_graphs() -> tuple[Graph, Graph]:
    knowledge = Graph()
    provenance = Graph()
    for uri in (PROP_A, PROP_B, PROP_EMPTY):
        knowledge.add((uri, RDF.type, SCI_NS.Proposition))
    knowledge.add((PROP_A, SKOS.prefLabel, Literal("Panel membership claim")))
    knowledge.add((HYP, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((HYP, SCI_NS.hasProposition, PROP_A))
    knowledge.add((HYP, SCI_NS.hasProposition, PROP_B))
    return knowledge, provenance


def test_profile_reuses_summary_empirical_type_semantics() -> None:
    assert is_empirical_evidence_type("empirical_data")
    assert is_empirical_evidence_type("empirical_data_evidence")
    assert is_empirical_evidence_type("benchmark")
    assert not is_empirical_evidence_type("literature")


def test_profile_emits_non_bundle_row_with_labels_and_null_scalar() -> None:
    knowledge, provenance = _base_graphs()
    _line(
        knowledge,
        provenance,
        PROP_A,
        "expert-a",
        evidence_type="expert_judgment",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/editorial-note"]),
        confidence=0.9,
    )

    rows = profile_records(knowledge, provenance, scalar_enabled=False)

    row = next(item for item in rows if item["entity"] == "proposition:pa")
    assert row == {
        "entity": "proposition:pa",
        "kind": "proposition",
        "label": "Panel membership claim",
        "belief_state": "fragile",
        "contested": False,
        "epistemic_labels": [
            "fragile",
            "single_source",
            "no_empirical_data",
            "authored_only",
        ],
        "evidence": {
            "support_count": 1,
            "dispute_count": 0,
            "diagnostic_count": 0,
            "source_count": 1,
            "evidence_types": ["expert_judgment"],
            "has_empirical_data": False,
        },
        "caps": {
            "authored_capped": False,
            "qa_dataset_capped": False,
            "capped_by_refutation": False,
        },
        "freshness_state": None,
        "belief_scalar": None,
    }


def test_profile_default_excludes_empty_rows_but_all_includes_them() -> None:
    knowledge, provenance = _base_graphs()

    default_entities = {row["entity"] for row in profile_records(knowledge, provenance, scalar_enabled=False)}
    all_entities = {
        row["entity"]
        for row in profile_records(knowledge, provenance, scalar_enabled=False, include_all=True)
    }

    assert "proposition:empty" not in default_entities
    assert "proposition:empty" in all_entities


def test_profile_bundle_summarizes_member_evidence_with_null_diagnostic_count() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_B,
        "lit-b",
        evidence_type="literature",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/b"]),
    )

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=False)
        if item["entity"] == "hypothesis:h1"
    )

    assert row["kind"] == "hypothesis"
    assert row["belief_state"] == "fragile"
    assert row["evidence"] == {
        "support_count": 2,
        "dispute_count": 0,
        "diagnostic_count": None,
        "source_count": 2,
        "evidence_types": ["empirical_data", "literature"],
        "has_empirical_data": True,
    }
    assert "empirical_data_backed" in row["epistemic_labels"]


def test_profile_filters_kind_and_repeated_labels_with_and_semantics() -> None:
    knowledge, provenance = _base_graphs()
    _line(
        knowledge,
        provenance,
        PROP_A,
        "expert-a",
        evidence_type="expert_judgment",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/editorial-note"]),
        confidence=0.9,
    )
    _line(knowledge, provenance, PROP_B, "emp-b", source=str(PROJECT_NS["source/b"]))

    rows = profile_records(
        knowledge,
        provenance,
        scalar_enabled=False,
        kinds=("proposition",),
        labels=("fragile", "no_empirical_data"),
    )

    assert [row["entity"] for row in rows] == ["proposition:pa"]


def test_profile_rejects_unknown_labels() -> None:
    knowledge, provenance = _base_graphs()

    import pytest

    with pytest.raises(ValueError, match="unknown belief profile label"):
        profile_records(knowledge, provenance, scalar_enabled=False, labels=("fragil",))


def test_profile_freshness_and_refutation_labels() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "support-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_A,
        "support-b",
        source=str(PROJECT_NS["source/b"]),
        group="support-b",
    )
    _line(
        knowledge,
        provenance,
        PROP_A,
        "refute-a",
        stance="disputes",
        source=str(PROJECT_NS["source/c"]),
        group="refute-a",
        dispute_scope="whole_claim",
    )
    knowledge.add((PROP_A, SCI_NS.freshnessState, Literal("needs-review")))

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=False)
        if item["entity"] == "proposition:pa"
    )

    assert row["belief_state"] == "fragile"
    assert row["contested"] is False
    assert row["caps"]["capped_by_refutation"] is True
    assert row["freshness_state"] == "needs-review"
    assert "capped_by_refutation" in row["epistemic_labels"]
    assert "needs_review" in row["epistemic_labels"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.graph.belief_profile'`.

- [ ] **Step 3: Create the profile module**

Create `science/src/science_tool/graph/belief_profile.py`:

```python
from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rdflib import RDF, URIRef
from rdflib.namespace import SKOS

from .belief import BeliefResult, EvidenceUnit, is_authored_assertion
from .belief_scalar import BeliefScalar, belief_scalar, belief_scalar_enabled
from .belief_weights import normalize_evidence_type
from .bundle_belief import BundleBeliefResult, belief_for_entity, bundle_kind
from .io import PROJECT_NS, SCI_NS, project_root_from_graph_path
from .store import _graph_uri, _load_dataset
from .store.summary import is_empirical_evidence_type

SUPPORTED_KINDS: tuple[str, ...] = ("proposition", "hypothesis", "mechanism")
PROFILE_LABELS: tuple[str, ...] = (
    "speculative",
    "fragile",
    "supported",
    "well_supported",
    "contested",
    "single_source",
    "no_empirical_data",
    "authored_only",
    "literature_only",
    "empirical_data_backed",
    "authored_capped",
    "qa_dataset_capped",
    "capped_by_refutation",
    "stale",
    "needs_review",
)
_KIND_TYPES = {
    "proposition": SCI_NS.Proposition,
    "hypothesis": SCI_NS.Hypothesis,
    "mechanism": SCI_NS.Mechanism,
}


@dataclass(frozen=True)
class _EvidenceSummary:
    support_count: int
    dispute_count: int
    diagnostic_count: int | None
    source_count: int
    evidence_types: list[str]
    has_empirical_data: bool
    support_units: tuple[EvidenceUnit, ...]
    all_units: tuple[EvidenceUnit, ...]

    def payload(self) -> dict[str, Any]:
        return {
            "support_count": self.support_count,
            "dispute_count": self.dispute_count,
            "diagnostic_count": self.diagnostic_count,
            "source_count": self.source_count,
            "evidence_types": self.evidence_types,
            "has_empirical_data": self.has_empirical_data,
        }


def _belief_entity_uris(knowledge) -> list[URIRef]:
    seen: set[URIRef] = set()
    rows: list[URIRef] = []
    for kind in SUPPORTED_KINDS:
        for uri, _, _ in knowledge.triples((None, RDF.type, _KIND_TYPES[kind])):
            if isinstance(uri, URIRef) and uri not in seen:
                seen.add(uri)
                rows.append(uri)
    return sorted(rows, key=str)


def _entity_kind(knowledge, uri: URIRef) -> str | None:
    if (uri, RDF.type, SCI_NS.Proposition) in knowledge:
        return "proposition"
    return bundle_kind(knowledge, uri)


def _entity_ref(uri: URIRef) -> str:
    value = str(uri)
    prefix = str(PROJECT_NS)
    if value.startswith(prefix):
        suffix = value[len(prefix):]
        if "/" in suffix:
            kind, slug = suffix.split("/", 1)
            if kind and slug:
                return f"{kind}:{slug}"
    return value


def _label_for_entity(knowledge, uri: URIRef) -> str:
    label = next(knowledge.objects(uri, SKOS.prefLabel), None)
    if label is not None:
        return str(label)
    text = next(knowledge.objects(uri, SCI_NS.text), None)
    if text is not None:
        return str(text)
    return _entity_ref(uri)


def _freshness_state(knowledge, uri: URIRef) -> str | None:
    value = next(knowledge.objects(uri, SCI_NS.freshnessState), None)
    return str(value) if value is not None else None


def _unique_sources(units: Iterable[EvidenceUnit]) -> int:
    return len({unit.source for unit in units if unit.source})


def _evidence_types(units: Iterable[EvidenceUnit]) -> list[str]:
    return sorted({normalize_evidence_type(unit.evidence_type) for unit in units if unit.evidence_type})


def _evidence_summary(result: BeliefResult | BundleBeliefResult) -> _EvidenceSummary:
    if isinstance(result, BundleBeliefResult):
        support_units = tuple(unit for member in result.member_results for unit in member.belief.support_units)
        dispute_units = tuple(unit for member in result.member_results for unit in member.belief.dispute_units)
        diagnostic_units = tuple(unit for member in result.member_results for unit in member.belief.diagnostics)
        all_units = (*support_units, *dispute_units, *diagnostic_units)
        diagnostic_count: int | None = None
    else:
        support_units = tuple(result.support_units)
        dispute_units = tuple(result.dispute_units)
        diagnostic_units = tuple(result.diagnostics)
        all_units = (*support_units, *dispute_units, *diagnostic_units)
        diagnostic_count = len(diagnostic_units)

    types = _evidence_types(all_units)
    return _EvidenceSummary(
        support_count=len(support_units),
        dispute_count=len(dispute_units),
        diagnostic_count=diagnostic_count,
        source_count=_unique_sources(all_units),
        evidence_types=types,
        has_empirical_data=any(is_empirical_evidence_type(value) for value in types),
        support_units=support_units,
        all_units=all_units,
    )


def _scalar_payload(scalar: BeliefScalar | None) -> dict[str, Any] | None:
    if scalar is None:
        return None
    return {
        "massed_support_score": scalar.massed_support_score,
        "massed_dispute_score": scalar.massed_dispute_score,
        "massed_support_band": list(scalar.massed_support_band),
        "massed_dispute_band": list(scalar.massed_dispute_band),
        "net_band": list(scalar.net_band),
        "net_robust": scalar.net_robust,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
    }


def _belief_scalar_payload(result: BeliefResult | BundleBeliefResult, *, scalar_enabled: bool) -> dict[str, Any] | None:
    if not scalar_enabled:
        return None
    if isinstance(result, BundleBeliefResult):
        return _scalar_payload(result.scalar)
    return _scalar_payload(belief_scalar(result))


def _caps_payload(result: BeliefResult | BundleBeliefResult) -> dict[str, bool]:
    return {
        "authored_capped": result.authored_capped,
        "qa_dataset_capped": result.qa_dataset_capped,
        "capped_by_refutation": result.capped_by_refutation,
    }


def _labels(
    result: BeliefResult | BundleBeliefResult,
    evidence: _EvidenceSummary,
    *,
    freshness_state: str | None,
) -> list[str]:
    labels: list[str] = [result.magnitude.value]
    if result.contested:
        labels.append("contested")
    if evidence.support_count + evidence.dispute_count > 0 and evidence.source_count == 1:
        labels.append("single_source")
    if evidence.support_count + evidence.dispute_count > 0 and not evidence.has_empirical_data:
        labels.append("no_empirical_data")
    if evidence.has_empirical_data:
        labels.append("empirical_data_backed")
    if evidence.support_units and all(is_authored_assertion(unit) for unit in evidence.support_units):
        labels.append("authored_only")

    normalized_types = {
        normalize_evidence_type(unit.evidence_type)
        for unit in evidence.all_units
        if unit.evidence_type
    }
    if normalized_types == {"literature"}:
        labels.append("literature_only")

    if result.authored_capped:
        labels.append("authored_capped")
    if result.qa_dataset_capped:
        labels.append("qa_dataset_capped")
    if result.capped_by_refutation:
        labels.append("capped_by_refutation")
    if freshness_state == "stale":
        labels.append("stale")
    if freshness_state == "needs-review":
        labels.append("needs_review")

    return list(dict.fromkeys(labels))


def _default_include(
    result: BeliefResult | BundleBeliefResult,
    evidence: _EvidenceSummary,
    *,
    freshness_state: str | None,
) -> bool:
    if isinstance(result, BundleBeliefResult) and result.member_results:
        # Deliberate design tradeoff: resolved bundles are informative by membership
        # even when all member propositions are still evidence-free.
        return True
    if not isinstance(result, BundleBeliefResult):
        diagnostic_count = evidence.diagnostic_count or 0
        if evidence.support_count + evidence.dispute_count + diagnostic_count > 0:
            return True
    if result.authored_capped or result.qa_dataset_capped or result.capped_by_refutation:
        return True
    return freshness_state in {"needs-review", "stale"}


def profile_records(
    knowledge,
    provenance,
    *,
    scalar_enabled: bool,
    include_all: bool = False,
    kinds: Sequence[str] = (),
    labels: Sequence[str] = (),
) -> list[dict[str, Any]]:
    requested_kinds = set(kinds)
    requested_labels = set(labels)
    unknown_labels = requested_labels - set(PROFILE_LABELS)
    if unknown_labels:
        raise ValueError(f"unknown belief profile label(s): {', '.join(sorted(unknown_labels))}")
    rows: list[dict[str, Any]] = []

    for uri in _belief_entity_uris(knowledge):
        kind = _entity_kind(knowledge, uri)
        if kind is None:
            continue
        if requested_kinds and kind not in requested_kinds:
            continue

        result = belief_for_entity(knowledge, provenance, uri, scalar_enabled=scalar_enabled)
        evidence = _evidence_summary(result)
        freshness = _freshness_state(knowledge, uri)
        row_labels = _labels(result, evidence, freshness_state=freshness)

        if not include_all and not _default_include(result, evidence, freshness_state=freshness):
            continue
        if requested_labels and not requested_labels.issubset(set(row_labels)):
            continue

        rows.append({
            "entity": _entity_ref(uri),
            "kind": kind,
            "label": _label_for_entity(knowledge, uri),
            "belief_state": result.magnitude.value,
            "contested": result.contested,
            "epistemic_labels": row_labels,
            "evidence": evidence.payload(),
            "caps": _caps_payload(result),
            "freshness_state": freshness,
            "belief_scalar": _belief_scalar_payload(result, scalar_enabled=scalar_enabled),
        })

    rows.sort(key=lambda row: row["entity"])
    return rows


def make_profiles(
    graph_path: Path,
    *,
    include_all: bool = False,
    kinds: Sequence[str] = (),
    labels: Sequence[str] = (),
) -> list[dict[str, Any]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))
    enabled = belief_scalar_enabled(project_root_from_graph_path(graph_path))
    return profile_records(
        knowledge,
        provenance,
        scalar_enabled=enabled,
        include_all=include_all,
        kinds=kinds,
        labels=labels,
    )
```

- [ ] **Step 4: Run the profile tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/graph/belief_profile.py science/tests/test_belief_profile.py
rtk git commit -m "feat: derive belief profile rows"
```

## Task 3: Scalar Projection Coverage

**Files:**
- Modify: `science/tests/test_belief_profile.py`

- [ ] **Step 1: Add scalar-enabled tests**

Append these tests to `science/tests/test_belief_profile.py`:

```python
def _expected_scalar_payload(knowledge: Graph, provenance: Graph, target: URIRef) -> dict:
    from science_tool.graph.belief import aggregate_belief, collect_evidence_units
    from science_tool.graph.belief_scalar import belief_scalar

    scalar = belief_scalar(aggregate_belief(collect_evidence_units(knowledge, provenance, [target])))
    return {
        "massed_support_score": scalar.massed_support_score,
        "massed_dispute_score": scalar.massed_dispute_score,
        "massed_support_band": list(scalar.massed_support_band),
        "massed_dispute_band": list(scalar.massed_dispute_band),
        "net_band": list(scalar.net_band),
        "net_robust": scalar.net_robust,
        "diagnostic_dispute_count": scalar.diagnostic_dispute_count,
    }


def test_profile_projects_existing_scalar_for_non_bundle_when_enabled() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=True)
        if item["entity"] == "proposition:pa"
    )

    assert row["belief_scalar"] == _expected_scalar_payload(knowledge, provenance, PROP_A)


def test_profile_projects_existing_bundle_scalar_driver_when_enabled() -> None:
    knowledge, provenance = _base_graphs()
    _line(knowledge, provenance, PROP_A, "emp-a", source=str(PROJECT_NS["source/a"]))
    _line(
        knowledge,
        provenance,
        PROP_B,
        "lit-b",
        evidence_type="literature",
        evidence_role="background_constraint",
        strength="moderate",
        source=str(PROJECT_NS["source/b"]),
    )

    row = next(
        item
        for item in profile_records(knowledge, provenance, scalar_enabled=True)
        if item["entity"] == "hypothesis:h1"
    )

    assert row["belief_scalar"] == _expected_scalar_payload(knowledge, provenance, PROP_B)
```

These tests must compare the profile output to the existing scalar engine. If a
failure shows only a scalar score or band mismatch, update the test expectation
to match `belief_scalar(aggregate_belief(...))`; do not change
`science/src/science_tool/graph/belief_scalar.py` to satisfy profile tests.

- [ ] **Step 2: Run the scalar tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py::test_profile_projects_existing_scalar_for_non_bundle_when_enabled science/tests/test_belief_profile.py::test_profile_projects_existing_bundle_scalar_driver_when_enabled -q
```

Expected: PASS. A scalar-value-only mismatch means the test is not using the
current engine output; fix the test, not the scalar engine.

- [ ] **Step 3: Run the full profile test file**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```bash
rtk git add science/tests/test_belief_profile.py
rtk git commit -m "test: cover belief profile scalar projection"
```

## Task 4: CLI Command

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_belief_cli.py`

- [ ] **Step 1: Add the failing CLI test**

Append this test to `science/tests/test_belief_cli.py`:

```python
def test_belief_profile_emits_json_query_rows(tmp_path: Path, monkeypatch):
    from science_tool.graph import belief_profile

    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True)
    graph_path.write_text("", encoding="utf-8")

    canned = [{
        "entity": "proposition:pa",
        "kind": "proposition",
        "label": "Panel membership claim",
        "belief_state": "fragile",
        "contested": False,
        "epistemic_labels": ["fragile", "single_source"],
        "evidence": {
            "support_count": 1,
            "dispute_count": 0,
            "diagnostic_count": 0,
            "source_count": 1,
            "evidence_types": ["expert_judgment"],
            "has_empirical_data": False,
        },
        "caps": {
            "authored_capped": False,
            "qa_dataset_capped": False,
            "capped_by_refutation": False,
        },
        "freshness_state": None,
        "belief_scalar": None,
    }]
    calls = []

    def fake_make_profiles(path, *, include_all=False, kinds=(), labels=()):
        calls.append((path, include_all, kinds, labels))
        return canned

    monkeypatch.setattr(belief_profile, "make_profiles", fake_make_profiles)

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "belief",
            "profile",
            "--path",
            str(graph_path),
            "--format",
            "json",
            "--all",
            "--kind",
            "proposition",
            "--label",
            "fragile",
            "--label",
            "single_source",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [(graph_path, True, ("proposition",), ("fragile", "single_source"))]

    import json

    payload = json.loads(result.output)
    assert payload["format"] == "json"
    assert payload["rows"] == canned
    assert payload["meta"] == {
        "count": 1,
        "include_all": True,
        "kinds": ["proposition"],
        "labels": ["fragile", "single_source"],
    }
```

- [ ] **Step 2: Run the CLI test to verify it fails**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_cli.py::test_belief_profile_emits_json_query_rows -q
```

Expected: FAIL with click output indicating there is no `profile` command under `belief`.

- [ ] **Step 3: Wire the command**

In `science/src/science_tool/cli.py`, change:

```python
from science_tool.graph import belief_snapshot
```

to:

```python
from science_tool.graph import belief_profile, belief_snapshot
```

Then insert this helper and command immediately after `belief_snapshot_cmd()`:

```python
def _belief_profile_table_row(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row["evidence"]
    caps = row["caps"]
    cap_labels = [name for name, active in caps.items() if active]
    return {
        "entity": row["entity"],
        "kind": row["kind"],
        "belief_state": row["belief_state"],
        "contested": "yes" if row["contested"] else "no",
        "labels": ", ".join(row["epistemic_labels"]) or "-",
        "support": evidence["support_count"],
        "dispute": evidence["dispute_count"],
        "diagnostic": "-" if evidence["diagnostic_count"] is None else evidence["diagnostic_count"],
        "sources": evidence["source_count"],
        "empirical": "yes" if evidence["has_empirical_data"] else "no",
        "caps": ", ".join(cap_labels) or "-",
        "freshness": row["freshness_state"] or "-",
        "label": row["label"],
    }


@belief_group.command("profile")
@click.option(
    "--path",
    "graph_path",
    default=str(DEFAULT_GRAPH_PATH),
    show_default=True,
    type=click.Path(path_type=Path),
)
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option(
    "--kind",
    "kinds",
    multiple=True,
    type=click.Choice(belief_profile.SUPPORTED_KINDS),
    help="Entity kind filter; repeatable.",
)
@click.option(
    "--label",
    "labels",
    multiple=True,
    type=click.Choice(belief_profile.PROFILE_LABELS),
    help="Epistemic label filter; repeatable with AND semantics.",
)
@click.option("--all", "include_all", is_flag=True, help="Include every supported belief-bearing entity.")
def belief_profile_cmd(
    graph_path: Path,
    output_format: str,
    kinds: tuple[str, ...],
    labels: tuple[str, ...],
    include_all: bool,
) -> None:
    """List derived epistemic profiles for belief-bearing entities."""
    rows = belief_profile.make_profiles(
        graph_path,
        include_all=include_all,
        kinds=kinds,
        labels=labels,
    )
    emit_rows = rows if output_format == "json" else [_belief_profile_table_row(row) for row in rows]
    emit_query_rows(
        output_format=output_format,
        title="Belief Profile",
        columns=[
            ("entity", "Entity"),
            ("kind", "Kind"),
            ("belief_state", "Belief"),
            ("contested", "Contested"),
            ("labels", "Labels"),
            ("support", "Support"),
            ("dispute", "Dispute"),
            ("diagnostic", "Diagnostic"),
            ("sources", "Sources"),
            ("empirical", "Empirical"),
            ("caps", "Caps"),
            ("freshness", "Freshness"),
            ("label", "Label"),
        ],
        rows=emit_rows,
        meta={
            "count": len(rows),
            "include_all": include_all,
            "kinds": list(kinds),
            "labels": list(labels),
        },
    )
```

- [ ] **Step 4: Run the CLI test**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_cli.py::test_belief_profile_emits_json_query_rows -q
```

Expected: PASS.

- [ ] **Step 5: Run profile and CLI tests together**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py science/tests/test_belief_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_belief_cli.py
rtk git commit -m "feat: add belief profile cli"
```

## Task 5: Documentation Status

**Files:**
- Modify: `docs/plans/2026-06-23-belief-profile-design.md`

- [ ] **Step 1: Update design status**

In `docs/plans/2026-06-23-belief-profile-design.md`, change:

```markdown
**Status:** Design approved in brainstorming; implementation not started.
```

to:

```markdown
**Status:** Implementation planned; see `docs/plans/2026-06-23-belief-profile-implementation-plan.md`.
```

- [ ] **Step 2: Verify the docs diff**

Run:

```bash
rtk git diff -- docs/plans/2026-06-23-belief-profile-design.md
```

Expected: only the status line changes.

- [ ] **Step 3: Commit**

Run:

```bash
rtk git add docs/plans/2026-06-23-belief-profile-design.md
rtk git commit -m "docs: mark belief profile implementation planned"
```

## Task 6: Final Verification

**Files:**
- No planned edits.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
rtk uv run --frozen pytest science/tests/test_belief_profile.py science/tests/test_belief_cli.py science/tests/test_bundle_belief_snapshot.py science/tests/test_belief_policy_persistence.py -q
```

Expected: PASS.

- [ ] **Step 2: Run ruff on touched files**

Run:

```bash
rtk uv run --frozen ruff check science/src/science_tool/graph/belief_profile.py science/src/science_tool/graph/store/summary.py science/src/science_tool/cli.py science/tests/test_belief_profile.py science/tests/test_belief_cli.py
```

Expected: PASS.

- [ ] **Step 3: Run formatting check on touched Python files**

Run:

```bash
rtk uv run --frozen ruff format --check science/src/science_tool/graph/belief_profile.py science/src/science_tool/graph/store/summary.py science/src/science_tool/cli.py science/tests/test_belief_profile.py science/tests/test_belief_cli.py
```

Expected: PASS.

- [ ] **Step 4: Run the command against the project graph**

Run:

```bash
rtk uv run --frozen science belief profile --format json
```

Expected: exit 0 and JSON with this shape:

```json
{
  "format": "json",
  "rows": [],
  "meta": {
    "count": 0,
    "include_all": false,
    "kinds": [],
    "labels": []
  }
}
```

The row count may be greater than zero on a populated graph. The shape and metadata keys must match exactly.

- [ ] **Step 5: Inspect final status**

Run:

```bash
rtk git status --short
```

Expected: no modified tracked files. The pre-existing untracked file `docs/plans/2026-06-23-science-citations-and-references-design.md` may still appear and must remain untouched unless the user separately asks to handle it.

## Self-Review

Spec coverage:

- Queryable per-entity epistemic profile: Task 2.
- Default row set and `--all`: Task 2 and Task 4.
- Supported kinds and `--kind`: Task 2 and Task 4.
- Repeated `--label` with AND semantics: Task 2 and Task 4.
- Existing belief path reuse: Task 2 uses `belief_for_entity()`.
- Bundle asymmetry and `diagnostic_count: null`: Task 2.
- Existing scalar only: Task 3.
- Empirical semantics reuse: Task 1 and Task 2.
- CLI JSON/table output: Task 4.
- Documentation status: Task 5.

Placeholder scan:

- This plan has no deferred implementation markers and no unspecified validation or edge-case instructions. Every code-changing task includes exact code or exact replacement text.

Type consistency:

- `profile_records()` and `make_profiles()` signatures match all test and CLI call sites.
- `caps.capped_by_refutation`, `authored_capped`, and `qa_dataset_capped` match existing `BeliefResult` and `BundleBeliefResult` fields.
- `freshness_state` uses graph literal tokens and maps only `needs-review` to the filter label `needs_review`.
