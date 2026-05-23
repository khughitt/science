# Independence-Aware Evidence Aggregation → Belief State (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the count-based `_belief_state` rollup with an independence-aware aggregation that reads per-line `evidence-line` metadata, collapses non-independent **same-stance** lines, applies scoped refutation precedence, and derives an **ordinal belief magnitude + an orthogonal `contested` flag**; then ship belief-level QA checks (#3/#4/#5/#6) and dogfood it on the cancer-evolution h012↔Simeonov2021 pilot.

**Architecture:** A new pure module `graph/belief.py` aggregates in five stages mirroring design §2 (collect units → stance-aware collapse by independence → ordinal quality classification + proxy gate → scoped refutation precedence → ladder assembly). It reads each line's **cito edge + rdf:type from the `knowledge` graph** and its **metadata from the `provenance` graph** (this is where `_add_reasoning_metadata` writes — materialize.py:771-783). `store.py` calls it in place of `_belief_state` via the existing `_claim_summary_data(knowledge, provenance, uri)` signature; the ordinal `belief_state` (magnitude) and a new `contested` flag flow into `ClaimSummaryData`. The belief QA checks compare **authored/frontmatter** confidence against the **computed** ceiling (the aggregator self-caps, so computed-vs-computed would be tautological — they must check authored overreach). DRY: one aggregator, no second belief path.

**Tech Stack:** Python 3.12, pydantic v2, rdflib, jsonschema, pytest, `uv`. Two packages: `science-model` (`science/model/`, tests `science/model/tests/`, run `cd science/model && uv run pytest …`) and `science_tool` (`science/`, tests `science/tests/`, run `cd science && uv run pytest …`).

**Spec:** `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` (rev 2026-05-22c) — implements §2 (rules 1–5), §3 (belief ladder), QA #3/#4/#5/#6.

## Dependency on Phase 0 (read before starting)

Phase 0 (`2026-05-22-evidence-line-entity-phase0-plan.md`) is **not implemented on any branch** — the `evidence-line-belief-design` branch carries only docs. This plan **cannot execute until Phase 0 lands**. Phase 1 consumes the following Phase-0 deliverables; they are stated here as explicit, verified-against-current-tree assumptions (correcting the earlier draft):

- **Graph routing (verified):** entity `rdf:type` and `cito:supports`/`cito:disputes` edges live in the **`knowledge`** graph; per-line reasoning metadata lives in the **`provenance`** graph, written by `_add_reasoning_metadata` keyed by the line URI (materialize.py:236, 771-783). Phase 1 reads accordingly.
- **Per-line predicates Phase 0 must materialize to provenance under the line URI:** the already-emitted `sci:evidenceRole`, `sci:independenceGroup`, `sci:proxyDirectness`, `sci:measurementModel` (materialize.py:775-792), **plus** Phase-0-new `sci:evidenceStrength`, `sci:evidenceIndependence`, `sci:disputeScope`, `sci:sharedDataset`/`sci:sharedLab`/`sci:sharedPlatform`/`sci:sharedCohort`, and `sci:evidenceType`.
- **Evidence-type vocabulary (verified):** canonical values carry the `_evidence` suffix — `literature_evidence`, `empirical_data_evidence`, `benchmark_evidence`, etc. (cli.py:1646-1649; `proposition.md` template; materialized via `SCI_NS.evidenceType` to provenance, store.py:656). The aggregator normalizes by stripping the suffix.
- **Model facts (verified — do NOT re-add):** `ProxyDirectness` (reasoning.py:39) and `proxy_directness` (entities.py:268) already exist on the generic model. All reasoning fields except `evidence_role` are on **base `Entity`** (entities.py:266-271: `claim_layer`, `identification_strength`, `proxy_directness`, `supports_scope`, `independence_group`, `measurement_model`); **`evidence_role` is `ProjectEntity`-only** (entities.py:362) and `_add_reasoning_metadata` emits it via `getattr`, so it reaches the graph **only when the entity is a `ProjectEntity` subclass**. Therefore Phase 0 must construct the `evidence-line` kind as a `ProjectEntity`-class entity (via typed dispatch) so `sci:evidenceRole` (and the other ProjectEntity reasoning fields) materialize. Phase 1 builds no entity class.
- **The evidence-line rdf:type class URI** (e.g. `SCI_NS.EvidenceLine`) is whatever Phase 0's materializer mints — confirm it in Task 3 Step 2 and set the module constant to match.

**Branch:** continue on `evidence-line-belief-design` after Phase 0 lands (or `evidence-belief-phase1` off it). **All commits local; do NOT push.** A subagent in a worktree MUST `cd` to the worktree path and verify the branch before committing.

**Key design rule (design §Prerequisite):** aggregation counts **only** `cito:` edges whose subject is an `evidence-line` entity. Bare cito edges from other subjects are surfaced by Phase 0's `evidence.unstanced`/uncounted-source check, never silently counted as support. Fail-loud, no legacy-count fallback.

**Stance-aware collapse (decision, this plan):** within one `independence_group`, only **same-stance** concordant lines collapse to the strongest. If a group holds **both** a support and a dispute, both winners are kept, the group is marked a **contested independence unit**, and its support winner is **barred from counting as clean concordant support** (cannot promote a claim to `well_supported`). Opposite-stance evidence never cancels — contestation is surfaced, not settled.

**Scope guard (NOT in Phase 1):** numeric `belief_weight`/`influence_weight` (the `attention.py:250-251` `None` placeholders stay), leave-one-out (#7), golden byte-reproducibility (#8), belief snapshots, `sci:edgeStatus`/`sci:Posterior` migration, calibration backtest (#10), `core/decisions.md` opt-in. Phase 1 is **ordinal only**.

---

### Task 1: Parse base-`Entity` reasoning metadata from frontmatter (current-tree gap)

`_add_reasoning_metadata` (materialize.py:771) *emits* the reasoning fields to provenance via `getattr`, but `entity_kwargs` (frontmatter.py:312-352) **never parses them**, so they are `None` on every authored entity and never reach the graph. The aggregator reads them — fix the parse for the fields that live on **base `Entity`** (entities.py:266-271): `claim_layer`, `identification_strength`, `proxy_directness`, `supports_scope`, `independence_group`, `measurement_model`. (No new entity class, no new enum.)

**`evidence_role` is excluded from this task on purpose:** it is `ProjectEntity`-only (entities.py:362), and `parse_entity_file` returns base `Entity` for propositions (frontmatter.py:360), so it cannot attach to a base-`Entity` entity. The aggregator reads `evidence_role` from **evidence-line** entities, which Phase 0 constructs as a `ProjectEntity`-class kind with typed dispatch that parses and materializes `sci:evidenceRole`. That parsing is a Phase 0 deliverable; Phase 1 verifies it round-trips (Task 3 collector test + Task 11 e2e).

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py:312-352` (`entity_kwargs`)
- Test: `science/model/tests/test_frontmatter.py`, `science/tests/test_reasoning_metadata_materialize.py`

- [ ] **Step 1: Confirm the gap + field locations** — `rg -n "claim_layer|independence_group|proxy_directness|measurement_model" science/model/src/science_model/frontmatter.py` (expect no hits in the `entity_kwargs` block). Confirm the six fields are on base `Entity` and `evidence_role` is on `ProjectEntity`: `rg -n "class Entity\b|class ProjectEntity\b|claim_layer|independence_group|proxy_directness|measurement_model|evidence_role" science/model/src/science_model/entities.py`.
- [ ] **Step 2: Failing test** — author a temp markdown (base-`Entity` kind) with `independence_group` + `proxy_directness`; `parse_entity_file` it; assert those attributes are set (not `None`). **Do not assert `evidence_role`** — that needs the ProjectEntity path. Run → FAIL.

```python
def test_base_entity_reasoning_fields_parse_from_frontmatter(tmp_path):
    from science_model.frontmatter import parse_entity_file
    p = tmp_path / "doc" / "propositions" / "p.md"
    p.parent.mkdir(parents=True)
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    p.write_text(
        "---\nid: proposition:p\ntype: proposition\n"
        "independence_group: g1\nproxy_directness: indirect\nclaim_layer: mechanism\n---\n# P\n",
        encoding="utf-8",
    )
    ent = parse_entity_file(p)
    assert ent.independence_group == "g1"
    assert str(ent.proxy_directness) == "indirect"
    assert str(ent.claim_layer) == "mechanism"
```

- [ ] **Step 3: Parse the fields** — add to the `entity_kwargs` dict (frontmatter.py:312-352), mirroring the existing `fm.get(...)` style (pydantic v2 coerces `StrEnum` fields from their string value):

```python
        "claim_layer": fm.get("claim_layer"),
        "identification_strength": fm.get("identification_strength"),
        "proxy_directness": fm.get("proxy_directness"),
        "supports_scope": fm.get("supports_scope"),
        "independence_group": fm.get("independence_group"),
        "measurement_model": fm.get("measurement_model"),
```

Note `evidence_role` is intentionally NOT added here (ProjectEntity-only). If a future need arises to carry `evidence_role` on propositions, that is a separate model decision (move it to `Entity`, or add typed proposition dispatch) — out of scope for Phase 1.
- [ ] **Step 4: Materialization round-trip test** — in `test_reasoning_metadata_materialize.py` (idiom: `test_chain_materialize.py`), author the proposition, `materialize_graph(tmp_path)`, parse `.trig`, assert the **provenance** graph contains `(proposition:p, sci:independenceGroup, "g1")` and `(proposition:p, sci:proxyDirectness, "indirect")`.
- [ ] **Step 5:** `cd science/model && uv run pytest` and `cd science && uv run pytest tests/test_reasoning_metadata_materialize.py -v` green.
- [ ] **Step 6:** Commit `fix(model): parse base-Entity reasoning metadata from frontmatter into entity_kwargs`.

> **Phase-0 boundary:** `evidence_role` (ProjectEntity), plus `strength`, `independence`, `dispute_scope`, and the `shared_*` observability fields (not on the generic model at all), are introduced and materialized by Phase 0 on the evidence-line kind (`sci:evidenceRole`/`sci:evidenceStrength`/`sci:evidenceIndependence`/`sci:disputeScope`/`sci:shared*`). Phase 1 only consumes them (Task 3).

---

### Task 2: Vocabulary + ordinal rank tables with `_evidence` normalization

**Files:**
- Create: `science/src/science_tool/graph/belief_weights.py`
- Test: `science/tests/test_belief_weights.py`

- [ ] **Step 1: Failing test** — assert the ordering and that normalization strips the `_evidence` suffix so both authored forms rank identically.

```python
from science_tool.graph import belief_weights as bw

def test_normalization_handles_evidence_suffix():
    assert bw.normalize_evidence_type("empirical_data_evidence") == "empirical_data"
    assert bw.normalize_evidence_type("empirical_data") == "empirical_data"
    assert bw.normalize_evidence_type(None) == ""

def test_type_ordering_via_rank():
    rank = lambda v: bw.EVIDENCE_TYPE_RANK.get(bw.normalize_evidence_type(v), 0)
    assert rank("empirical_data_evidence") > rank("simulation_evidence")
    assert rank("simulation_evidence") == rank("benchmark_evidence")
    assert rank("simulation_evidence") > rank("literature_evidence")
    assert rank("literature_evidence") > rank("expert_judgment_evidence")

def test_role_and_strength_ordering():
    assert bw.EVIDENCE_ROLE_RANK["direct_test"] > bw.EVIDENCE_ROLE_RANK["proxy_support"]
    assert bw.EVIDENCE_ROLE_RANK["proxy_support"] > bw.EVIDENCE_ROLE_RANK["background_constraint"]
    assert bw.STRENGTH_RANK["strong"] > bw.STRENGTH_RANK["moderate"] > bw.STRENGTH_RANK["weak"]

def test_diagnostic_roles():
    assert {"model_criticism", "negative_control"} <= bw.DIAGNOSTIC_ROLES
    assert "direct_test" not in bw.DIAGNOSTIC_ROLES
```

- [ ] **Step 2: Implement** `belief_weights.py`:

```python
"""Fixed ordinal rankings for evidence quality (design §2 rule 2, Phase 1).

Ordering is fixed here; per-project numeric weights and the quantitative scalar are
Phase 2 (opt-in via core/decisions.md). Unknown values rank 0 (degrade gracefully).
Canonical evidence_type values carry an '_evidence' suffix (cli.py:1646); we normalize.
"""
from __future__ import annotations

STANCE_SUPPORTS = "supports"
STANCE_DISPUTES = "disputes"

ROLE_DIRECT_TEST = "direct_test"
ROLE_PROXY_SUPPORT = "proxy_support"
ROLE_BACKGROUND = "background_constraint"
ROLE_NEGATIVE_CONTROL = "negative_control"
ROLE_MODEL_CRITICISM = "model_criticism"

INDEPENDENT = "independent"
SHARED_SOURCE = "shared-source"
CIRCULAR = "circular"

SCOPE_WHOLE_CLAIM = "whole_claim"
GATED_PROXY = frozenset({"indirect", "derived"})
DIAGNOSTIC_ROLES = frozenset({ROLE_NEGATIVE_CONTROL, ROLE_MODEL_CRITICISM})

_EVIDENCE_SUFFIX = "_evidence"

# Keyed on NORMALIZED (suffix-stripped) tokens.
EVIDENCE_TYPE_RANK = {
    "empirical_data": 4,
    "benchmark": 3,
    "simulation": 3,
    "literature": 2,
    "expert_judgment": 1,
}
EVIDENCE_ROLE_RANK = {ROLE_DIRECT_TEST: 3, ROLE_PROXY_SUPPORT: 2, ROLE_BACKGROUND: 1}
STRENGTH_RANK = {"strong": 3, "moderate": 2, "weak": 1}


def normalize_evidence_type(value: str | None) -> str:
    if not value:
        return ""
    return value[: -len(_EVIDENCE_SUFFIX)] if value.endswith(_EVIDENCE_SUFFIX) else value
```

- [ ] **Step 3:** Tests green; commit `feat(graph): ordinal evidence-quality rank tables + evidence_type normalization`.

---

### Task 3: Collect per-line evidence units (`belief.py`, stage 1)

Reads cito edge + rdf:type from `knowledge`; metadata from `provenance`.

**Files:**
- Create: `science/src/science_tool/graph/belief.py`
- Test: `science/tests/test_belief_collect.py`

- [ ] **Step 1: Failing test** — build a `knowledge` graph (type + cito edge) and a `provenance` graph (metadata); assert one `EvidenceUnit` with fields from provenance; assert a non-evidence-line cito subject is ignored.

```python
from rdflib import Graph, URIRef, Literal, RDF
from science_tool.graph.io import SCI_NS, CITO_NS
from science_tool.graph.belief import collect_evidence_units, EVIDENCE_LINE_CLASS

CLAIM = URIRef("http://example.org/science/entity/proposition/p")
LINE = URIRef("http://example.org/science/entity/evidence-line/e")
BARE = URIRef("http://example.org/science/entity/observation/o")

def test_collects_line_metadata_from_provenance():
    knowledge, provenance = Graph(), Graph()
    knowledge.add((LINE, RDF.type, EVIDENCE_LINE_CLASS))
    knowledge.add((LINE, CITO_NS.disputes, CLAIM))
    knowledge.add((BARE, CITO_NS.supports, CLAIM))            # not a line → ignored
    provenance.add((LINE, SCI_NS.evidenceStrength, Literal("strong")))
    provenance.add((LINE, SCI_NS.evidenceIndependence, Literal("independent")))
    provenance.add((LINE, SCI_NS.independenceGroup, Literal("g1")))
    provenance.add((LINE, SCI_NS.evidenceRole, Literal("model_criticism")))
    provenance.add((LINE, SCI_NS.disputeScope, Literal("generalization")))
    provenance.add((LINE, SCI_NS.evidenceType, Literal("empirical_data_evidence")))
    units = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert len(units) == 1
    u = units[0]
    assert u.stance == "disputes" and u.strength == "strong" and u.independence == "independent"
    assert u.independence_group == "g1" and u.evidence_role == "model_criticism"
    assert u.dispute_scope == "generalization" and u.evidence_type == "empirical_data_evidence"
```

Run → FAIL.

- [ ] **Step 2: Confirm the type URI + source predicate** — `rg -n "EvidenceLine|evidence-line|wasDerivedFrom" science/src/science_tool/graph/materialize.py`. Set `EVIDENCE_LINE_CLASS` to the class URI Phase 0 mints (expected `SCI_NS.EvidenceLine`). Confirm whether the line's source is `prov:wasDerivedFrom` (provenance) and adjust `_read_unit`’s `source` lookup.
- [ ] **Step 3: Implement** the unit model + collector:

```python
"""Independence-aware evidence aggregation → ordinal belief (design §2/§3, Phase 1)."""
from __future__ import annotations

from dataclasses import dataclass

from rdflib import Graph, RDF, URIRef

from .io import CITO_NS, SCI_NS

EVIDENCE_LINE_CLASS = SCI_NS.EvidenceLine  # confirm against Phase 0 materializer (Task 3 Step 2)


@dataclass(frozen=True)
class EvidenceUnit:
    line_uri: str
    stance: str                       # "supports" | "disputes"
    strength: str | None
    independence: str | None
    independence_group: str | None
    evidence_role: str | None
    evidence_type: str | None
    dispute_scope: str | None
    proxy_directness: str | None
    has_measurement_model: bool
    source: str | None
    observability_keys: tuple[str, ...]


_OBSERVABILITY = {
    "shared_dataset": SCI_NS.sharedDataset,
    "shared_lab": SCI_NS.sharedLab,
    "shared_platform": SCI_NS.sharedPlatform,
    "shared_cohort": SCI_NS.sharedCohort,
}


def _lit(graph: Graph, subject: URIRef, predicate: URIRef) -> str | None:
    for _, _, value in graph.triples((subject, predicate, None)):
        return str(value)
    return None


def _read_unit(provenance: Graph, line: URIRef, stance: str) -> EvidenceUnit:
    obs = tuple(name for name, pred in _OBSERVABILITY.items() if _lit(provenance, line, pred))
    return EvidenceUnit(
        line_uri=str(line),
        stance=stance,
        strength=_lit(provenance, line, SCI_NS.evidenceStrength),
        independence=_lit(provenance, line, SCI_NS.evidenceIndependence),
        independence_group=_lit(provenance, line, SCI_NS.independenceGroup),
        evidence_role=_lit(provenance, line, SCI_NS.evidenceRole),
        evidence_type=_lit(provenance, line, SCI_NS.evidenceType),
        dispute_scope=_lit(provenance, line, SCI_NS.disputeScope),
        proxy_directness=_lit(provenance, line, SCI_NS.proxyDirectness),
        has_measurement_model=_lit(provenance, line, SCI_NS.measurementModel) is not None,
        source=_lit(provenance, line, getattr(SCI_NS, "evidenceSource")) or None,  # adjust per Step 2
        observability_keys=obs,
    )


def collect_evidence_units(
    knowledge: Graph, provenance: Graph, targets: "Iterable[URIRef]"
) -> list[EvidenceUnit]:
    """Counted units are ONLY cito edges whose subject is an evidence-line (design §Prerequisite).

    Edge + rdf:type are read from `knowledge`; per-line metadata from `provenance`.
    `targets` is the expanded target set — a hypothesis must be expanded to itself plus its
    linked claims via store's `_evidence_targets_for_uri` (store.py:3498) so hypothesis belief
    sees proposition-level evidence (matches `_collect_evidence_signals`). Lines are de-duped by
    URI so a line bearing on multiple targets counts once.
    """
    units: list[EvidenceUnit] = []
    seen: set[str] = set()
    for target in targets:
        for predicate, stance in ((CITO_NS.supports, "supports"), (CITO_NS.disputes, "disputes")):
            for subject, _, _ in knowledge.triples((None, predicate, target)):
                if (subject, RDF.type, EVIDENCE_LINE_CLASS) not in knowledge:
                    continue
                if str(subject) in seen:
                    continue
                seen.add(str(subject))
                units.append(_read_unit(provenance, subject, stance))
    return units
```

`Iterable` import: add `from collections.abc import Iterable` to `belief.py`. Callers pass `_evidence_targets_for_uri(knowledge, uri)` (store.py and the QA check), keeping target expansion in `store.py` and `belief.py` free of a circular import.

- [ ] **Step 4:** `cd science && uv run pytest tests/test_belief_collect.py -v` green.
- [ ] **Step 5:** Commit `feat(graph): collect per-line evidence units (knowledge edge + provenance metadata)`.

---

### Task 4: Stance-aware independence collapse (`belief.py`, stage 2 — design §2 rule 1 + this plan's decision)

**Files:**
- Modify: `science/src/science_tool/graph/belief.py`
- Test: `science/tests/test_belief_reduce.py`

- [ ] **Step 1: Failing test** — assert: (a) two same-stance `shared-source` lines in one group collapse to the strongest; (b) a `circular` line is excluded; (c) a `shared-source`/`circular` line with no group is flagged and not counted; (d) two `independent` supports survive as two units; (e) **a support and a dispute in the same group are BOTH kept and the group is reported in `contested_groups`** (opposite stances never cancel).

```python
from science_tool.graph.belief import EvidenceUnit, reduce_units

def _u(**kw):
    base = dict(line_uri="x", stance="supports", strength="moderate", independence="independent",
                independence_group=None, evidence_role="proxy_support", evidence_type="literature_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

def test_same_stance_shared_source_collapses_to_strongest():
    weak = _u(line_uri="a", independence="shared-source", independence_group="g1", strength="weak")
    strong = _u(line_uri="b", independence="shared-source", independence_group="g1",
                strength="strong", evidence_type="empirical_data_evidence", evidence_role="direct_test")
    r = reduce_units([weak, strong])
    assert [u.line_uri for u in r.kept] == ["b"]
    assert len(r.collapsed) == 1
    assert r.contested_groups == set()

def test_circular_excluded_and_ungrouped_flagged():
    circ = _u(line_uri="c", independence="circular", independence_group="g1")
    ungrouped = _u(line_uri="d", independence="shared-source", independence_group=None)
    r = reduce_units([circ, ungrouped])
    assert r.kept == []
    assert [u.line_uri for u in r.excluded_circular] == ["c"]
    assert [u.line_uri for u in r.flagged_ungrouped] == ["d"]

def test_two_independents_survive():
    r = reduce_units([_u(line_uri="a", independence_group="g1"), _u(line_uri="b", independence_group="g2")])
    assert len(r.kept) == 2

def test_opposite_stance_same_group_both_kept_and_contested():
    sup = _u(line_uri="s", independence_group="g1", stance="supports")
    dis = _u(line_uri="d", independence_group="g1", stance="disputes")
    r = reduce_units([sup, dis])
    assert {u.line_uri for u in r.kept} == {"s", "d"}
    assert r.contested_groups == {"g1"}
```

Run → FAIL.

- [ ] **Step 2: Implement** `quality_key` + `reduce_units` (append to `belief.py`):

```python
from .belief_weights import (
    CIRCULAR, EVIDENCE_ROLE_RANK, EVIDENCE_TYPE_RANK, SHARED_SOURCE,
    STRENGTH_RANK, normalize_evidence_type,
)


def quality_key(u: "EvidenceUnit") -> tuple[int, int, int]:
    return (
        EVIDENCE_TYPE_RANK.get(normalize_evidence_type(u.evidence_type), 0),
        EVIDENCE_ROLE_RANK.get(u.evidence_role or "", 0),
        STRENGTH_RANK.get(u.strength or "", 0),
    )


@dataclass
class ReducedUnits:
    kept: list["EvidenceUnit"]            # per (group, stance) winner + each ungrouped line
    collapsed: list["EvidenceUnit"]       # same-stance shared-source lines dropped
    excluded_circular: list["EvidenceUnit"]
    flagged_ungrouped: list["EvidenceUnit"]
    contested_groups: set[str]            # real groups holding BOTH a support and a dispute winner


def reduce_units(units: list["EvidenceUnit"]) -> ReducedUnits:
    excluded_circular: list[EvidenceUnit] = []
    flagged_ungrouped: list[EvidenceUnit] = []
    collapsed: list[EvidenceUnit] = []
    winners: dict[tuple[str, str], EvidenceUnit] = {}      # (group_or_line_token, stance) -> winner
    real_groups_by_stance: dict[str, set[str]] = {"supports": set(), "disputes": set()}

    for u in units:
        if u.independence in (SHARED_SOURCE, CIRCULAR) and not u.independence_group:
            flagged_ungrouped.append(u)                    # "collapse to what?" undefined (QA #2b)
            continue
        if u.independence == CIRCULAR:
            excluded_circular.append(u)
            continue
        if u.independence_group:
            key = (u.independence_group, u.stance)
            real_groups_by_stance[u.stance].add(u.independence_group)
        else:
            key = (f"__line__:{u.line_uri}", u.stance)      # ungrouped lines never merge
        if key not in winners:
            winners[key] = u
        elif quality_key(u) > quality_key(winners[key]):
            collapsed.append(winners[key])
            winners[key] = u
        else:
            collapsed.append(u)

    contested_groups = real_groups_by_stance["supports"] & real_groups_by_stance["disputes"]
    return ReducedUnits(
        kept=list(winners.values()),
        collapsed=collapsed,
        excluded_circular=excluded_circular,
        flagged_ungrouped=flagged_ungrouped,
        contested_groups=contested_groups,
    )
```

- [ ] **Step 3:** `cd science && uv run pytest tests/test_belief_reduce.py -v` green.
- [ ] **Step 4:** Commit `feat(graph): stance-aware independence collapse (rule 1)`.

---

### Task 5: Quality classification + proxy gate (`belief.py`, stage 3 — design §2 rules 2 & 5)

**Files:**
- Modify: `science/src/science_tool/graph/belief.py`
- Test: `science/tests/test_belief_classify.py`

- [ ] **Step 1: Failing test:**

```python
from science_tool.graph.belief import EvidenceUnit, is_qualifying_direct_test, is_diagnostic, is_proxy_gated

def _u(**kw):
    base = dict(line_uri="x", stance="supports", strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

def test_direct_test_qualifies():
    assert is_qualifying_direct_test(_u()) is True

def test_proxy_gate_blocks_ungated_proxy():
    assert is_proxy_gated(_u(proxy_directness="indirect")) is True
    assert is_qualifying_direct_test(_u(proxy_directness="indirect")) is False
    assert is_qualifying_direct_test(_u(proxy_directness="indirect", has_measurement_model=True)) is True

def test_model_criticism_is_diagnostic():
    assert is_diagnostic(_u(evidence_role="model_criticism")) is True
    assert is_diagnostic(_u(evidence_role="direct_test")) is False
```

Run → FAIL.

- [ ] **Step 2: Implement** (append to `belief.py`):

```python
from .belief_weights import DIAGNOSTIC_ROLES, GATED_PROXY, ROLE_DIRECT_TEST


def is_diagnostic(u: "EvidenceUnit") -> bool:
    """negative_control / model_criticism: separate ledger rows, never FOR/AGAINST mass."""
    return (u.evidence_role or "") in DIAGNOSTIC_ROLES


def is_proxy_gated(u: "EvidenceUnit") -> bool:
    """Rule 5: indirect/derived proxy with no measurement_model cannot contribute at full weight."""
    return (u.proxy_directness or "") in GATED_PROXY and not u.has_measurement_model


def is_qualifying_direct_test(u: "EvidenceUnit") -> bool:
    return u.evidence_role == ROLE_DIRECT_TEST and not is_proxy_gated(u)
```

- [ ] **Step 3:** `cd science && uv run pytest tests/test_belief_classify.py -v` green.
- [ ] **Step 4:** Commit `feat(graph): evidence quality classification + proxy gate (rules 2 & 5)`.

---

### Task 6: Scoped refutation precedence (`belief.py`, stage 4 — design §2 rule 3)

**Files:**
- Modify: `science/src/science_tool/graph/belief.py`
- Test: `science/tests/test_belief_refutation.py`

- [ ] **Step 1: Failing test:**

```python
from science_tool.graph.belief import EvidenceUnit, is_decisive_refutation

def _d(**kw):
    base = dict(line_uri="x", stance="disputes", strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope="whole_claim", proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

def test_whole_claim_direct_test_strong_is_decisive():
    assert is_decisive_refutation(_d()) is True

def test_scoped_or_criticism_or_weak_is_not_decisive():
    assert is_decisive_refutation(_d(dispute_scope="generalization")) is False
    assert is_decisive_refutation(_d(evidence_role="model_criticism")) is False
    assert is_decisive_refutation(_d(strength="moderate")) is False
    assert is_decisive_refutation(_d(independence="shared-source")) is False
    assert is_decisive_refutation(_d(proxy_directness="indirect")) is False  # ungated proxy (rule 5)
```

Run → FAIL.

- [ ] **Step 2: Implement** (append to `belief.py`, after Task 5's helpers):

```python
from .belief_weights import INDEPENDENT, SCOPE_WHOLE_CLAIM


def is_decisive_refutation(u: "EvidenceUnit") -> bool:
    """Rule 3: ONLY an independent strong direct_test whole_claim dispute caps belief.

    whole_claim is the default when scope is unset; model_criticism and scoped disputes
    (generalization/mechanism/boundary) set `contested` but never eliminate. The proxy gate
    (rule 5) applies symmetrically: an ungated indirect/derived proxy direct-test cannot be
    decisive either (`is_qualifying_direct_test` already encodes role + proxy gate).
    """
    return (
        u.stance == "disputes"
        and u.independence == INDEPENDENT
        and u.strength == "strong"
        and is_qualifying_direct_test(u)
        and (u.dispute_scope or SCOPE_WHOLE_CLAIM) == SCOPE_WHOLE_CLAIM
    )
```

Because this now calls `is_qualifying_direct_test`, define `is_decisive_refutation` **after** Task 5's helpers in `belief.py` (or move the helper above it). Add a test asserting an `indirect` proxy dispute with no `measurement_model` is **not** decisive.

- [ ] **Step 3:** `cd science && uv run pytest tests/test_belief_refutation.py -v` green.
- [ ] **Step 4:** Commit `feat(graph): scoped refutation precedence (rule 3)`.

---

### Task 7: Belief ladder assembly (`belief.py`, stage 5 — design §3)

**Files:**
- Modify: `science/src/science_tool/graph/belief.py`
- Test: `science/tests/test_belief_aggregate.py`

- [ ] **Step 1: Failing test** — table over the ladder, including a contested-group case and the pilot shape:

```python
from science_tool.graph.belief import EvidenceUnit, BeliefMagnitude, aggregate_belief

def _u(stance="supports", **kw):
    base = dict(line_uri="x", stance=stance, strength="strong", independence="independent",
                independence_group="g", evidence_role="direct_test", evidence_type="empirical_data_evidence",
                dispute_scope=None, proxy_directness=None, has_measurement_model=False,
                source=None, observability_keys=())
    base.update(kw); return EvidenceUnit(**base)

def test_no_support_is_speculative():
    assert aggregate_belief([]).magnitude == BeliefMagnitude.SPECULATIVE

def test_single_unit_is_fragile():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1")])
    assert r.magnitude == BeliefMagnitude.FRAGILE and r.contested is False

def test_two_independents_with_direct_test_is_well_supported():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1"),
                          _u(line_uri="b", independence_group="g2")])
    assert r.magnitude == BeliefMagnitude.WELL_SUPPORTED

def test_two_independents_no_direct_test_is_supported():
    r = aggregate_belief([_u(line_uri="a", independence_group="g1", evidence_role="proxy_support"),
                          _u(line_uri="b", independence_group="g2", evidence_role="proxy_support")])
    assert r.magnitude == BeliefMagnitude.SUPPORTED

def test_contested_group_support_is_not_clean_corroboration():
    # one clean independent support + one group holding BOTH support and dispute
    clean = _u(line_uri="a", independence_group="g1")
    sup_c = _u(line_uri="b", independence_group="g2")
    dis_c = _u(stance="disputes", line_uri="c", independence_group="g2", dispute_scope="mechanism")
    r = aggregate_belief([clean, sup_c, dis_c])
    assert r.contested is True
    # g2's support is barred from clean direct-test corroboration; g1 alone -> not well_supported
    assert r.magnitude in (BeliefMagnitude.FRAGILE, BeliefMagnitude.SUPPORTED)

def test_decisive_refutation_caps_below_supported_and_contests():
    r = aggregate_belief([
        _u(line_uri="a", independence_group="g1"),
        _u(line_uri="b", independence_group="g2"),
        _u(stance="disputes", line_uri="d", independence_group="g3", dispute_scope="whole_claim"),
    ])
    assert r.contested is True and r.capped_by_refutation is True
    assert r.magnitude == BeliefMagnitude.FRAGILE

def test_pilot_shape_fragile_contested_not_eliminated():
    support = _u(line_uri="yang", independence_group="kp-tracer")
    criticism = _u(stance="disputes", line_uri="simeonov", independence_group="macsgestalt",
                   evidence_role="model_criticism", dispute_scope="generalization")
    r = aggregate_belief([support, criticism])
    assert r.magnitude == BeliefMagnitude.FRAGILE
    assert r.contested is True and r.capped_by_refutation is False
    assert r.display() == "fragile (contested)"
```

Run → FAIL.

- [ ] **Step 2: Implement** the magnitude enum + `aggregate_belief` (append to `belief.py`):

```python
from enum import StrEnum


class BeliefMagnitude(StrEnum):
    SPECULATIVE = "speculative"
    FRAGILE = "fragile"
    SUPPORTED = "supported"
    WELL_SUPPORTED = "well_supported"


_MAG_ORDER = [
    BeliefMagnitude.SPECULATIVE,
    BeliefMagnitude.FRAGILE,
    BeliefMagnitude.SUPPORTED,
    BeliefMagnitude.WELL_SUPPORTED,
]


@dataclass
class BeliefResult:
    magnitude: BeliefMagnitude
    contested: bool
    capped_by_refutation: bool
    support_units: list["EvidenceUnit"]
    dispute_units: list["EvidenceUnit"]
    diagnostics: list["EvidenceUnit"]
    contested_groups: set[str]
    excluded: list["EvidenceUnit"]
    flagged_ungrouped: list["EvidenceUnit"]

    def display(self) -> str:
        return f"{self.magnitude.value} (contested)" if self.contested else self.magnitude.value


def aggregate_belief(units: list["EvidenceUnit"]) -> BeliefResult:
    reduced = reduce_units(units)
    cg = reduced.contested_groups

    support = [u for u in reduced.kept if u.stance == "supports" and not is_diagnostic(u)]
    dispute = [u for u in reduced.kept if u.stance == "disputes" and not is_diagnostic(u)]
    diagnostics = [u for u in reduced.kept if is_diagnostic(u)]

    n_support = len(support)
    # A support unit in a contested group is not clean corroboration (stance-aware-collapse
    # decision): well_supported needs >=2 *clean* units, one of which is a qualifying direct test.
    clean_support = [u for u in support if u.independence_group not in cg]
    clean_direct_test = any(is_qualifying_direct_test(u) for u in clean_support)
    decisive = any(is_decisive_refutation(u) for u in dispute)

    if n_support == 0:
        magnitude = BeliefMagnitude.SPECULATIVE
    elif n_support == 1:
        magnitude = BeliefMagnitude.FRAGILE
    elif clean_direct_test and len(clean_support) >= 2:
        magnitude = BeliefMagnitude.WELL_SUPPORTED
    else:
        magnitude = BeliefMagnitude.SUPPORTED

    capped = False
    if decisive and _MAG_ORDER.index(magnitude) > _MAG_ORDER.index(BeliefMagnitude.FRAGILE):
        magnitude = BeliefMagnitude.FRAGILE
        capped = True

    contested = (
        bool(dispute)
        or any(u.stance == "disputes" for u in diagnostics)
        or bool(cg)
    )

    return BeliefResult(
        magnitude=magnitude,
        contested=contested,
        capped_by_refutation=capped,
        support_units=support,
        dispute_units=dispute,
        diagnostics=diagnostics,
        contested_groups=cg,
        excluded=reduced.excluded_circular,
        flagged_ungrouped=reduced.flagged_ungrouped,
    )
```

- [ ] **Step 3:** `cd science && uv run pytest tests/test_belief_aggregate.py -v` green.
- [ ] **Step 4:** Commit `feat(graph): ordinal belief ladder + contested flag (design §3)`.

---

### Task 8: Wire aggregation into `_claim_summary_data` (replace `_belief_state`)

The function already takes both graphs: `_claim_summary_data(knowledge, provenance, uri)` (store.py:3646). Replace the count-based `belief_state` (store.py:3655) with the aggregator and add a `contested` flag. Remove `_belief_state` (store.py:3614-3627).

**Files:**
- Modify: `science/src/science_tool/graph/store.py` (`_belief_state` removal; `_claim_summary_data` ~3646-3756; `ClaimSummaryData` TypedDict; `_format_claim_summary_row` 3759-3779)
- Test: `science/tests/test_belief_store_integration.py`

- [ ] **Step 1: Failing test** — materialize a project (idiom: `test_chain_materialize.py`) with one supporting evidence-line and one `model_criticism` disputing line on a proposition; load the dataset; call `_claim_summary_data(knowledge, provenance, claim_uri)`; assert `belief_state == "fragile"` and `contested is True`. (Asserting on the internal `ClaimSummaryData`, not the formatted row — the row stringifies and uses the `"claim"` key, not `"id"`.)

```python
def test_claim_summary_reports_fragile_contested(tmp_path):
    from rdflib import Dataset, URIRef
    from science_tool.graph.materialize import materialize_graph
    from science_tool.graph.store import _claim_summary_data, _graph_uri
    # ... write science.yaml + doc/propositions/p.md + two doc/evidence-lines/*.md ...
    materialize_graph(tmp_path)
    ds = Dataset(); ds.parse(source=str(tmp_path / "knowledge" / "graph.trig"), format="trig")
    knowledge = ds.graph(_graph_uri("graph/knowledge"))
    provenance = ds.graph(_graph_uri("graph/provenance"))
    claim = URIRef("http://example.org/science/entity/proposition/p")  # match the minted URI
    data = _claim_summary_data(knowledge, provenance, claim)
    assert data is not None
    assert data["belief_state"] == "fragile"          # machine field: magnitude only
    assert data["contested"] is True
    assert data["belief_display"] == "fragile (contested)"  # human headline
```

Run → FAIL.

- [ ] **Step 2: Add `contested` + `belief_display` to the shape** — add `contested: bool` and `belief_display: str` to the `ClaimSummaryData` TypedDict and to the dict returned by `_claim_summary_data` (alongside `"belief_state"` at store.py:3738). `belief_state` keeps the **magnitude string only** (machine field); `belief_display` is the human headline (`"fragile (contested)"` when contested, else just the magnitude). In `_format_claim_summary_row` (3759): render `"contested": "yes" if bool(summary["contested"]) else "no"` (matching `has_empirical_data` at 3771) and pass `"belief_display"` through as a string. The human-facing `science status` / dashboard belief column uses `belief_display`; structured/JSON consumers read `belief_state` + `contested` separately. This resolves the display contract: machine fields stay split, the headline composes them.
- [ ] **Step 3: Replace the rollup** — in `_claim_summary_data`, replace line 3655 (`belief_state = _belief_state(...)`) with (note the **target expansion** so a hypothesis aggregates its linked claims' evidence, matching `_collect_evidence_signals` at 3520):

```python
from .belief import aggregate_belief, collect_evidence_units

belief = aggregate_belief(
    collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, uri))
)
belief_state = belief.magnitude.value
contested = belief.contested
belief_display = belief.display()
```

`_evidence_targets_for_uri` already lives in `store.py` (3498) — no new import. Thread `contested` and `belief_display` into the returned dict. Keep the existing `support_count`/`dispute_count`/`source_count` columns (still computed by `_collect_evidence_signals`) — they are independent count columns, not the belief. Update the `signals` block (3683-3684) so the `"contested"` signal derives from `belief.contested` rather than `dispute_count > 0`. Delete `_belief_state` and its references.
- [ ] **Step 4: Sweep callers/tests** — `rg -n "_belief_state|belief_state|\"contested\"|'contested'" science/src science/tests`. Any test asserting the old semantics (e.g. `belief_state == "contested"` as a magnitude value) must move that assertion to the new `contested` field; the magnitude is now orthogonal (`speculative`/`fragile`/`supported`/`well_supported` only).
- [ ] **Step 5:** `cd science && uv run pytest tests/test_belief_store_integration.py -v` then full `cd science && uv run pytest` green.
- [ ] **Step 6:** Commit `refactor(graph): derive belief_state via independence-aware aggregation; add contested flag`.

---

### Task 9: Belief QA checks #3/#4/#5/#6 — authored vs. computed (extend Phase-0 `evidence_lines.py`)

The aggregator self-caps, so a computed-vs-computed invariant never fires (review finding 2). These checks compare **authored/frontmatter** confidence against the **computed** ceiling, and inspect line metadata directly. Load both `knowledge` and `provenance` graphs.

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py` (created in Phase 0)
- Modify: `science/src/science_tool/validate/gates.py` (`_TIER_RULES`)
- Test: `science/tests/test_evidence_line_belief_checks.py`

- [ ] **Step 1: Failing tests** — one fixture per rule:
  - `belief.single-source-ceiling` (WARN): frontmatter declares a magnitude above `fragile` but the graph yields one support independence unit → fires.
  - `belief.refutation-masked` (ERROR): frontmatter magnitude ≥ `supported` while an unresolved independent strong `direct_test` `whole_claim` dispute exists → fires; the same dispute as `model_criticism`/`generalization` does **not** fire.
  - `belief.inflated` (WARN): authored magnitude > computed magnitude → fires.
  - `evidence.proxy-ungated` (WARN): a counted support line with `proxy_directness ∈ {indirect, derived}`, no `measurement_model`, and `evidence_role == direct_test` → fires (inspects the line, independent of authored magnitude → reachable).
- [ ] **Step 2: Implement** the loader, the authored-magnitude reader, and the checks:

```python
from rdflib import Dataset, RDF, URIRef
from rdflib.namespace import PROV

from science_tool.graph.belief import (
    aggregate_belief, collect_evidence_units, is_decisive_refutation, is_proxy_gated,
    BeliefMagnitude,
)
from science_tool.graph.io import SCHEMA_NS, SCI_NS
from science_tool.graph.store import _evidence_targets_for_uri, _graph_uri
from ..result import Result, Severity
from . import Check

_MAG_INDEX = {m.value: i for i, m in enumerate(
    [BeliefMagnitude.SPECULATIVE, BeliefMagnitude.FRAGILE,
     BeliefMagnitude.SUPPORTED, BeliefMagnitude.WELL_SUPPORTED])}

# Authored prose/frontmatter phrasings → ladder rung. Unknown values are skipped (never guessed).
_AUTHORED_MAGNITUDE = {
    "speculative": "speculative", "proposed": "speculative",
    "fragile": "fragile", "single-source": "fragile",
    "supported": "supported", "literature-supported": "supported", "partially-supported": "supported",
    "well_supported": "well_supported", "well-supported": "well_supported", "established": "well_supported",
}


def _load_graphs(ctx):
    path = ctx.project_root / "knowledge" / "graph.trig"
    if not path.exists():
        return None, None
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds.graph(_graph_uri("graph/knowledge")), ds.graph(_graph_uri("graph/provenance"))


def _claims(knowledge):
    for ctype in (SCI_NS.Proposition, SCI_NS.Hypothesis):
        for subj, _, _ in knowledge.triples((None, RDF.type, ctype)):
            yield subj


def _authored_magnitude(ctx, provenance, claim_uri):
    """Map a claim's authored confidence (frontmatter) to a ladder rung.

    Returns (magnitude_str, path, None) or None. Resolution: in the provenance graph,
    (claim_uri, prov:wasDerivedFrom, source_uri) and (source_uri, schema:identifier,
    "<relative path>") (materialize.py:233,238). Reads belief_state / evidence_stance /
    author_stated_evidence; the leading token is mapped via _AUTHORED_MAGNITUDE; unknown
    phrasings are skipped (never guessed). Overlay sources are tolerated — first existing
    file wins.
    """
    for source in provenance.objects(claim_uri, PROV.wasDerivedFrom):
        rel = next(provenance.objects(source, SCHEMA_NS.identifier), None)
        if rel is None:
            continue
        path = ctx.project_root / str(rel)
        if not path.exists():
            continue
        fm = ctx.frontmatter(path)
        for field in ("belief_state", "evidence_stance", "author_stated_evidence"):
            raw = fm.get(field)
            if not raw:
                continue
            token = str(raw).strip().lower().split()[0].split("(")[0].strip("-_:")
            if token in _AUTHORED_MAGNITUDE:
                return _AUTHORED_MAGNITUDE[token], path, None
    return None


@Check(section="evidence & belief", order=23)
def check_belief_authoring(ctx):
    knowledge, provenance = _load_graphs(ctx)
    if knowledge is None:
        return
    for claim in _claims(knowledge):
        units = collect_evidence_units(knowledge, provenance, _evidence_targets_for_uri(knowledge, claim))
        belief = aggregate_belief(units)
        n_support_groups = len({u.independence_group or u.line_uri for u in belief.support_units})
        authored = _authored_magnitude(ctx, provenance, claim)
        decisive = any(is_decisive_refutation(u) for u in belief.dispute_units)

        # #6 evidence.proxy-ungated (line-level, both stances — rule 5 is symmetric)
        for u in (*belief.support_units, *belief.dispute_units):
            if is_proxy_gated(u) and u.evidence_role == "direct_test":
                yield Result(Severity.WARN, None, None,
                             f"{u.line_uri}: indirect/derived proxy as direct_test without a measurement_model",
                             "evidence.proxy-ungated", None)

        if authored is None:
            continue
        mag, path, line = authored
        if mag not in _MAG_INDEX:
            continue

        # #5 single-source-ceiling
        if n_support_groups <= 1 and _MAG_INDEX[mag] > _MAG_INDEX["fragile"]:
            yield Result(Severity.WARN, path, line,
                         f"authored '{mag}' exceeds single-independence-unit ceiling (fragile)",
                         "belief.single-source-ceiling", None)

        # #3 refutation-masked
        if decisive and _MAG_INDEX[mag] >= _MAG_INDEX["supported"]:
            yield Result(Severity.ERROR, path, line,
                         f"authored '{mag}' >= supported with an unresolved whole-claim refutation",
                         "belief.refutation-masked", None)

        # #4 inflated (general overreach vs computed)
        if _MAG_INDEX[mag] > _MAG_INDEX[belief.magnitude.value]:
            yield Result(Severity.WARN, path, line,
                         f"authored '{mag}' exceeds computed '{belief.magnitude.value}'",
                         "belief.inflated", None)
```

The URI→file resolution above is the verified mechanism (provenance `prov:wasDerivedFrom` → `schema:identifier` relative path → `ctx.frontmatter`). If `_graph_uri` is awkward to import from `store.py`, copy the one-line graph-name helper into `belief.py` and import it from there (single source). Extend `_AUTHORED_MAGNITUDE` only with phrasings actually present in the project's frontmatter — do not invent rungs for unseen phrases.

- [ ] **Step 3: Gate tiers** — add `"belief.refutation-masked"`, `"belief.single-source-ceiling"`, and `"evidence.proxy-ungated"` to `_TIER_RULES["hygiene"]` in `gates.py`. Leave `"belief.inflated"` ungated (advisory).
- [ ] **Step 4:** `cd science && uv run pytest tests/test_evidence_line_belief_checks.py -v` green; full suite green.
- [ ] **Step 5:** Commit `feat(validate): belief QA checks (refutation-masked, single-source-ceiling, inflated, proxy-ungated)`.

---

### Task 10: Pilot — re-author the cancer-evolution h012 evidence durably

Runs in the **separate** repo `~/d/cancer/mechanisms/evolution/` (its own git). Requires the framework changes above to be installed/available there. Note: per-line metadata materializes to the project's **provenance** graph.

**Files (in `~/d/cancer/mechanisms/evolution/`):**
- Create: `specs/evidence-lines/el-yang2022-h012-burst.md`
- Create: `specs/evidence-lines/el-simeonov2021-h012-criticism.md`
- Modify: `specs/propositions/h012-plasticity-burst-precedes-sweep.md` (trim prose-only stance language now that polarity is structured; do NOT inflate its authored magnitude)

- [ ] **Step 1: Supporting line** — `specs/evidence-lines/el-yang2022-h012-burst.md`:

```yaml
---
id: evidence-line:el-yang2022-h012-burst
type: evidence-line
stance: supports
target: proposition:h012-plasticity-burst-precedes-sweep
source: paper:Yang2022
strength: strong
evidence_type: empirical_data_evidence
evidence_role: direct_test
proxy_directness: direct
independence: independent
independence_group: kp-tracer-lineage
created: 2026-05-22
updated: 2026-05-22
---
## What this line shows
KP-Tracer continuous in vivo lineage tracing directly observes a plasticity burst →
stabilization → clonal sweep in KP LUAD.

## Why it is independent
KP-Tracer autochthonous mouse model; distinct platform/cohort from macsGESTALT.

## Caveats / scope
Demonstrated in KP LUAD only; generalization is open.
```

- [ ] **Step 2: Disputing line** — `specs/evidence-lines/el-simeonov2021-h012-criticism.md`:

```yaml
---
id: evidence-line:el-simeonov2021-h012-criticism
type: evidence-line
stance: disputes
target: proposition:h012-plasticity-burst-precedes-sweep
source: paper:Simeonov2021
strength: strong
evidence_type: empirical_data_evidence
evidence_role: model_criticism
dispute_scope: generalization
proxy_directness: direct
independence: independent
independence_group: macsgestalt-pdac
created: 2026-05-22
updated: 2026-05-22
---
## What this line shows
macsGESTALT in PDAC attributes hybrid-EMT enrichment to selection of pre-existing clones —
interpretive tension with a within-clone plasticity-burst mechanism.

## Why it is independent
Different cancer type (PDAC), platform (macsGESTALT), and cohort.

## Caveats / scope
Single 5-week endpoint with a triggered recorder cannot observe the plasticity-burst phase —
interpretive tension, not a data-level refutation. Scope: generalization, not whole_claim;
model_criticism, not a direct-test refutation.
```

- [ ] **Step 3: Build + validate** — in `~/d/cancer/mechanisms/evolution/`: `science graph build` then `science validate`. Expect both lines materialize as `cito:` edges (knowledge) with metadata in provenance; structural QA passes; **no** `belief.refutation-masked` ERROR (the dispute is `model_criticism`/`generalization`).
- [ ] **Step 4: Confirm belief** — `science status` shows `proposition:h012-plasticity-burst-precedes-sweep` with `belief_display = "fragile (contested)"` (machine fields: `belief_state = fragile`, `contested = yes`) — one clean support unit + one diagnostic (`model_criticism`) dispute, **not** capped-as-refuted (`capped_by_refutation` False). If it shows otherwise, STOP and debug the authored metadata or aggregation before committing.
- [ ] **Step 5:** Commit in the cancer-evolution repo: `feat(evidence): author h012 Yang2022/Simeonov2021 evidence-lines`. (Separate repo; do NOT push.)

---

### Task 11: End-to-end + docs + design-status bump

**Files:**
- Test: `science/tests/test_belief_e2e.py`
- Modify: `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` (roadmap status + resolved open questions)

- [ ] **Step 1: E2E test** — scaffold a project, `science entity create evidence-line` ×2 (one support `direct_test`; one `whole_claim` strong `direct_test` dispute), `science graph build`; assert the proposition's computed magnitude caps at `fragile` and that `belief.refutation-masked` fires when the proposition frontmatter authors `well_supported`; then switch the dispute to `model_criticism`/`generalization` and assert the ERROR clears and magnitude reflects support only.
- [ ] **Step 2: Doc bump** — mark **Phase 1** implemented (date) in the design roadmap. Record the resolved Phase-1 decisions inline: the ordinal rank table (Task 2), `_evidence` normalization, decisive-refutation cap behavior (cap to `fragile`, Task 7), and **stance-aware collapse** (opposite-stance same-group → both kept, group contested, support barred from clean corroboration). Leave the diminishing-returns curve and the negative_control/model_criticism-feeds-magnitude questions open for Phase 2.
- [ ] **Step 3:** `cd science && uv run pytest` full suite green.
- [ ] **Step 4:** Commit `test(graph): belief aggregation end-to-end; docs: mark Phase 1 done`.

---

## Exit criteria (Phase 1 done)

- `belief_state` is derived by `aggregate_belief` from per-line evidence-line units — read with the cito edge/type from `knowledge` and metadata from `provenance` — independence-collapsed **stance-aware**, quality-classified, proxy-gated, with scoped refutation precedence. `_belief_state` is gone.
- Belief is an **ordinal magnitude** (`speculative`/`fragile`/`supported`/`well_supported`) plus an **orthogonal `contested`** flag; machine consumers read them split, the human headline `belief_display` composes them (`"fragile (contested)"`). A decisive (independent strong, non-proxy-gated direct_test, whole_claim) dispute caps magnitude to `fragile`; `model_criticism`/scoped/ungated-proxy disputes set `contested` without capping; opposite-stance evidence in one independence_group never cancels and bars that unit from clean corroboration. Hypothesis belief expands to its linked claims' evidence.
- The four belief QA checks compare **authored vs. computed** (reachable, not tautological), are tier-gated as specified, and pass/flag correctly.
- The cancer-evolution pilot resolves `proposition:h012-plasticity-burst-precedes-sweep` to `fragile (contested)`, not eliminated.
- Both test suites green. No numeric scalar, leave-one-out, golden, snapshots, edge-status, posteriors, or `core/decisions.md` opt-in touched.

## Follow-on (NOT this plan)

- **Phase 2** — `belief_weight` `(support_mass, dispute_mass)` pair + net, leave-one-out (#7), golden byte-reproducibility (#8), append-only belief snapshots with input-hash sets; numeric weights opt-in via `core/decisions.md`. Fills `attention.py:250-251`.
- **Phase 3** — land `sci:edgeStatus`/`sci:Posterior` from YAML into the graph; aggregation sets `eliminated` via rule 3.
- **Phase 4** — calibration backtest (#10) + optional pgmpy CPDs.