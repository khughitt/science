# Pillar A2 — curation down-weight (`source_class: reference`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a supporting dataset's `source_class: reference` reach the belief scorer and apply a **bounded curation down-weight** — one ordinal step, floored at zero — to every evidence unit that rests on a human-curated reference artifact, landing **once** in the scalar (`unit_score`) and **once** in winner-selection (`quality_key`), and bump the belief config version.

**Architecture:** A `source_class` lives only in YAML/Pydantic/JSON-schema today (A1) — it never reaches the RDF graph the scorer reads. A2 builds the missing resolution path in four moves: (1) **materialize** `sci:sourceClass` onto dataset entity URIs in the `knowledge` graph; (2) **thread** a `is_reference_dataset` flag onto `EvidenceUnit` by checking each line's `prov:wasDerivedFrom` objects against the set of reference-dataset URIs; (3) **apply** `CURATION_STEP_PENALTY` in both scoring paths and bump `CONFIG_VERSION`; (4) add a **recording-only** `science validate` nudge that reference-as-basis evidence lines should declare `identification_strength: structural`. The penalty mirrors the existing `PROXY_STEP_PENALTY` precedent (`belief_weights.py`).

**Tech Stack:** Python 3.13, rdflib (TriG named graphs), Pydantic v2, pytest, `uv` workspace.

---

## Scope & deviations (read before starting)

This plan implements **A2** of design `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` (§8, decisions A-D4/A-D5, §4 resolved decision #3). A1 (the recording layer + `dataset_taxonomy` validate check) is already merged.

Three scope decisions, **confirmed with the user**, deviate from a literal reading of the design and are called out so the reviewer sees they are intentional:

1. **`identification_strength` is a *recording* nudge only — NOT wired into scoring.** The design (A-D2/A-D4) speaks of the "two-axis model" treating `structural` conservatively, but in the current code **`identification_strength` is not read by the scorer at all** (`EvidenceUnit` has no such field; it feeds display/migration only). Building the causal axis into `unit_score`/`quality_key` is a whole second numeric axis and a separate effort. A2 therefore ships only a soft `science validate` WARN nudging reference-as-basis lines toward `identification_strength: structural` (Task 4); it does **not** change scores based on `identification_strength`.

2. **Dataset-default modifier only — no per-line override.** Resolved decision #2 allows an auditable per-line override of the curation modifier. A2 derives the down-weight purely from the supporting dataset's `source_class` at scoring time (YAGNI: defer the override until a real case needs it). There is no per-line `curation_override` field in A2.

3. **The curation penalty lands in BOTH the scalar and winner-selection paths (per A-D4), but winner-selection is tiebreaker-only — a deliberate, documented narrowing.** `PROXY_STEP_PENALTY` is applied only in `unit_score` (`belief_scalar.py`), never in `quality_key`. A-D4 asks for the discount to "route through both the winner-selection path (`quality_key`) and the scalar/log-odds path (`unit_score`), so it lands exactly once in each." The scalar realization is the literal "subtract one ordinal score step, floored at 0." The **winner-selection** realization (Task 3) is a **least-significant tiebreaker demotion** and **explicitly scoped as tiebreaker-only in Phase 1**: `quality_key` gains a final tuple component so that, among units otherwise equal on `type > role > strength`, a reference-backed unit loses to a non-reference one; it does **not** demote across the `type/role/strength` tiers.

   **Why tiebreaker-only (the decision, not an open question):** `quality_key` is a **lexicographic** tuple `(type_rank, role_rank, strength_rank)` — `type` dominates entirely, so "subtract one ordinal step" is not even well-defined across tiers (a reference unit with higher `type` always outranks a non-reference one regardless of `strength`). The only way to make a *true* cross-tier one-step penalty meaningful in Phase 1 would be to **flatten `quality_key` to the summed-step scalar** (`type_steps + role_steps + strength_steps`, like `unit_score`) and penalize that — but doing so changes the winner-selection semantics for **every** unit (reference or not: lexicographic `type`-priority → additive trade-offs), an unrelated behavior change and regression risk that A2's "feed the existing machinery, don't rebuild it" principle forbids. So A2 keeps the established lexicographic ordering intact and applies curation as a tiebreaker only. The **scalar path carries the full epistemic weight** of the down-weight; Phase-1 winner-selection gets the conservative tiebreaker. **Task 5 records this verbatim in the design/status text ("tiebreaker-only in Phase 1 winner-selection").** Task 3's tests lock the semantics on both sides: a reference unit loses an exact tie, **and** a reference unit that is strictly stronger on any of `type/role/strength` still wins (proving the penalty does not cross tiers). If a reviewer wants the full flattened-scalar winner-selection penalty instead, that is a separate, larger change to Phase-1 semantics and should be its own plan.

It **must not** mutate `stance`, `strength`, `evidence_type`, independence grouping, or apply any `strength` cap (A-D4: no double-penalty). Bumping the belief config version (`belief-logodds-v1` → `-v2`) is required and **re-baselines stored belief snapshots in downstream projects** (the reproducibility check silently stops matching old-version rows — expected; downstream re-runs `belief-snapshot`).

**Resolution-path facts that make this work (verified against the code):**
- A dataset entity's URI and an evidence line's `prov:wasDerivedFrom` object for `source: dataset:foo` are **the same** `_entity_uri("dataset:foo")` = `PROJECT_NS["dataset/foo"]` (`materialize.py` `_entity_uri`, `_add_evidence_line_relations`).
- An evidence line carries **multiple** `prov:wasDerivedFrom` objects (its source *file* URI from `_add_entity`, **and** its source *entity* URI). The existing `EvidenceUnit.source` (`_lit`, first-wins) is therefore unreliable for this — Task 2 scans **all** of them.
- The `knowledge` graph (where Task 1 writes `sci:sourceClass`) is the exact graph every `collect_evidence_units(knowledge, provenance, …)` caller loads (`belief_snapshot.py`, `store/summary.py`, `attention.py`, `validate/checks/evidence_lines.py`).
- `SCI_NS` predicates need no write-time registration, but `sci:sourceClass` should be added to `PREDICATE_REGISTRY` and to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` (so its literal-valued triple is classified as entity metadata, not a structural edge, by `export_graph_payload`).

Shell commands are written plain; apply this repo's `rtk` convention per your runtime's own RTK instruction.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/graph/materialize.py` | sources → RDF | **Modify** `_add_entity`: emit `(uri, SCI_NS.sourceClass, Literal(...))` for dataset entities |
| `science/src/science_tool/graph/store/constants.py` | predicate registry / export classification | **Modify**: add `sci:sourceClass` to `PREDICATE_REGISTRY` + `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` |
| `science/src/science_tool/graph/belief.py` | Phase-1 aggregation | **Modify**: `EvidenceUnit.is_reference_dataset` field; `collect_evidence_units` builds the reference-URI set; `_read_unit` sets the flag; `quality_key` gains the demotion component |
| `science/src/science_tool/graph/belief_weights.py` | ordinal weights / constants | **Modify**: add `CURATION_STEP_PENALTY = 1`; bump `CONFIG_VERSION` to `belief-logodds-v2` |
| `science/src/science_tool/graph/belief_scalar.py` | Phase-2 log-odds scalar | **Modify** `unit_score`: apply the curation penalty (floored at 0) |
| `science/src/science_tool/validate/checks/evidence_lines.py` | evidence-line validate checks | **Modify**: add a graph-based WARN nudge (reference-basis → declare `identification_strength: structural`) |
| `science/tests/test_graph_materialize.py` (or `test_evidence_line_materialize.py`) | materialize tests | **Add** `sci:sourceClass` emission + same-URI resolution cases |
| `science/tests/test_graph_store.py` | store constants tests | **Add** `sci:sourceClass` membership cases |
| `science/tests/test_belief_collect.py` | collection tests | **Add** `is_reference_dataset` threading cases |
| `science/tests/test_belief_scalar.py` | scalar tests | **Add** curation-penalty cases |
| `science/tests/test_belief_weights.py` | constants tests | **Modify** `test_phase2_constants_present`; add `CURATION_STEP_PENALTY` |
| `science/tests/test_belief_reduce.py` | winner-selection tests | **Add** reference-demotion winner case |
| `science/tests/validate/test_checks_evidence_lines*.py` (match existing) | validate-check tests | **Add** structural-nudge cases |
| `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md`, `…-umbrella-design.md` | status | **Modify** (Task 5) |

**Test command (all tasks):** run from `~/d/science/science`:
```bash
cd ~/d/science/science && uv run pytest <path> -q
```

---

## Task 1: Materialize `sci:sourceClass` on dataset entities + register the predicate

Emit the dataset's epistemic class into the `knowledge` graph so the scorer can read it, and declare the predicate in the store registries.

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_entity`)
- Modify: `science/src/science_tool/graph/store/constants.py` (`PREDICATE_REGISTRY`, `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`)
- Test: `science/tests/test_graph_store.py`; a materialize test (`test_graph_materialize.py` or `test_evidence_line_materialize.py` — whichever already exercises entity → triple emission; read first and match its harness)

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_graph_store.py`, add membership assertions (this file already imports `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` and `SCI_NS`; match the existing `sci:scope` assertion idiom at the top of the file):

```python
def test_source_class_is_edge_metadata_predicate():
    from science_tool.graph.io import SCI_NS
    from science_tool.graph.store.constants import GRAPH_EXPORT_EDGE_METADATA_PREDICATES

    assert SCI_NS.sourceClass in GRAPH_EXPORT_EDGE_METADATA_PREDICATES


def test_source_class_in_predicate_registry():
    from science_tool.graph.store.constants import PREDICATE_REGISTRY

    assert any(entry["predicate"] == "sci:sourceClass" for entry in PREDICATE_REGISTRY)
```

In the materialize test file (READ it first to find how it builds entities and runs materialization; reuse that harness), add a test that a dataset entity with `source_class` emits the triple into `knowledge`, AND that an evidence line whose `source` is that dataset resolves to the **same** URI in `provenance`. Express the assertions as:

```python
# Pseudocode shape — adapt to the file's existing fixture/builder for materializing entities.
# Build a dataset entity `dataset:refset` with origin=external, source_class="reference",
# and an evidence-line entity with source="dataset:refset". Materialize to a Dataset.
# knowledge = dataset.graph(graph/knowledge); provenance = dataset.graph(graph/provenance)
from rdflib import Literal
from science_tool.graph.io import SCI_NS, PROJECT_NS
from rdflib.namespace import PROV

ds_uri = PROJECT_NS["dataset/refset"]
assert (ds_uri, SCI_NS.sourceClass, Literal("reference")) in knowledge
# the line's source resolves to the SAME dataset URI (one of its wasDerivedFrom objects):
line_derived = {o for _, _, o in provenance.triples((line_uri, PROV.wasDerivedFrom, None))}
assert ds_uri in line_derived
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/d/science/science && uv run pytest tests/test_graph_store.py -q -k source_class
```
Expected: FAIL (`assert … in GRAPH_EXPORT_EDGE_METADATA_PREDICATES` / registry miss). The materialize test fails because `_add_entity` does not yet emit `sci:sourceClass`.

- [ ] **Step 3: Emit the triple in `_add_entity`**

In `science/src/science_tool/graph/materialize.py`, inside `_add_entity`, after the existing `knowledge.add((uri, SCI_NS.projectStatus, …))` block and before the `source_uri = _source_uri(entity.file_path)` line, add (`SCI_NS` and `Literal` are already imported here):

```python
    if entity.kind == "dataset" and entity.source_class:
        knowledge.add((uri, SCI_NS.sourceClass, Literal(entity.source_class)))
```

(`entity.source_class` is `None` for non-dataset and unset datasets — the `and entity.source_class` guard skips both. A1 guarantees every dataset Entity carries the field on both load paths.)

- [ ] **Step 4: Register the predicate**

In `science/src/science_tool/graph/store/constants.py`:
- Add `SCI_NS.sourceClass` to the `GRAPH_EXPORT_EDGE_METADATA_PREDICATES` frozenset (alongside `SCI_NS.scope`).
- Add an entry to `PREDICATE_REGISTRY` (match the existing dict shape), grouped near other `sci:` entity-metadata predicates:

```python
    {"predicate": "sci:sourceClass",
     "description": "Dataset epistemic source class (observational | derived | reference)",
     "layer": "graph/knowledge"},
```

- [ ] **Step 5: Run to verify PASS**

```bash
cd ~/d/science/science && uv run pytest tests/test_graph_store.py tests/test_graph_materialize.py tests/test_evidence_line_materialize.py -q
```
Expected: PASS (new + pre-existing). No existing test asserts an exhaustive triple set, so adding the triple is non-breaking.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/src/science_tool/graph/store/constants.py science/tests/test_graph_store.py science/tests/test_graph_materialize.py science/tests/test_evidence_line_materialize.py
git commit -m "feat(graph): materialize sci:sourceClass on dataset entities (A2)"
```
(Stage only the materialize test file you actually edited.)

---

## Task 2: Thread `is_reference_dataset` onto `EvidenceUnit`

Detect, at collection time, whether an evidence line rests on a `reference` dataset, and record it on the unit. The penalty itself is Task 3.

**Files:**
- Modify: `science/src/science_tool/graph/belief.py` (`EvidenceUnit`, `_read_unit`, `collect_evidence_units`)
- Test: `science/tests/test_belief_collect.py`

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_belief_collect.py` (READ it first to match how it builds `knowledge`/`provenance` Graphs and a `CLAIM`/evidence-line; reuse that harness). Add two tests:

```python
# A line whose source is a dataset carrying sci:sourceClass "reference" → is_reference_dataset True.
def test_reference_source_sets_is_reference_dataset():
    # ... build per the file's harness:
    #   knowledge: (line, rdf:type, EvidenceLine), (line, cito:supports, CLAIM),
    #              (dataset_uri, sci:sourceClass, Literal("reference"))
    #   provenance: (line, prov:wasDerivedFrom, dataset_uri)
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.is_reference_dataset is True


def test_non_reference_source_leaves_flag_false():
    #   dataset_uri carries sci:sourceClass "observational" (or no sourceClass triple)
    (u,) = collect_evidence_units(knowledge, provenance, [CLAIM])
    assert u.is_reference_dataset is False
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/d/science/science && uv run pytest tests/test_belief_collect.py -q -k reference
```
Expected: FAIL (`AttributeError: 'EvidenceUnit' object has no attribute 'is_reference_dataset'`).

- [ ] **Step 3: Add the field, the lookup, and the threading**

In `science/src/science_tool/graph/belief.py`:

(a) Add `Literal` to the rdflib import:
```python
from rdflib import Graph, Literal, RDF, URIRef
```

(b) Add the field as the **last** field of `EvidenceUnit` (frozen dataclass), with a default so existing keyword constructions keep working:
```python
    observability_keys: tuple[str, ...]
    is_reference_dataset: bool = False
```

(c) Change `_read_unit` to take the reference-URI set and scan **all** `prov:wasDerivedFrom` objects (not first-wins):
```python
def _read_unit(
    provenance: Graph, line: URIRef, stance: str, reference_dataset_uris: frozenset[str]
) -> EvidenceUnit:
    obs = tuple(name for name, pred in _OBSERVABILITY.items() if _lit(provenance, line, pred))
    derived_from = {str(o) for _, _, o in provenance.triples((line, PROV.wasDerivedFrom, None))}
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
        source=_lit(provenance, line, PROV.wasDerivedFrom),
        observability_keys=obs,
        is_reference_dataset=bool(derived_from & reference_dataset_uris),
    )
```

(d) In `collect_evidence_units`, build the reference-URI set once from `knowledge` and pass it through:
```python
def collect_evidence_units(
    knowledge: Graph, provenance: Graph, targets: Iterable[URIRef]
) -> list[EvidenceUnit]:
    reference_dataset_uris = frozenset(
        str(s) for s, _, _ in knowledge.triples((None, SCI_NS.sourceClass, Literal("reference")))
    )
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
                units.append(_read_unit(provenance, subject, stance, reference_dataset_uris))
    return units
```

(All four call sites of `collect_evidence_units` already pass `knowledge`, so no caller changes. `_read_unit` is called only here.)

- [ ] **Step 4: Run to verify PASS**

```bash
cd ~/d/science/science && uv run pytest tests/test_belief_collect.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/belief.py science/tests/test_belief_collect.py
git commit -m "feat(belief): detect reference-dataset-backed evidence units (A2)"
```

---

## Task 3: Apply `CURATION_STEP_PENALTY` in both paths + bump `CONFIG_VERSION`

The down-weight itself: one ordinal step, floored at zero, in the scalar (`unit_score`) and as a tiebreaker demotion in winner-selection (`quality_key`).

**Files:**
- Modify: `science/src/science_tool/graph/belief_weights.py`
- Modify: `science/src/science_tool/graph/belief_scalar.py` (`unit_score`)
- Modify: `science/src/science_tool/graph/belief.py` (`quality_key`)
- Test: `science/tests/test_belief_scalar.py`, `science/tests/test_belief_weights.py`, `science/tests/test_belief_reduce.py`

- [ ] **Step 1: Write the failing tests**

In `science/tests/test_belief_scalar.py` (the `_u(**kw)` helper already exists; it accepts arbitrary keyword overrides, so `_u(is_reference_dataset=True)` works once the field exists):

```python
def test_reference_dataset_lowers_score_by_one():
    assert unit_score(_u(is_reference_dataset=True)) == 6           # 7 - 1
    # floored at zero, and never negative even with a minimal unit:
    assert unit_score(_u(evidence_role="background_constraint", strength="weak",
                         evidence_type="literature", is_reference_dataset=True)) == 0   # 1 - 1


def test_proxy_and_curation_penalties_stack():
    gated_ref = _u(proxy_directness="indirect", has_measurement_model=False,
                   is_reference_dataset=True)
    assert unit_score(gated_ref) == 4                               # 7 - 2 - 1
```

In `science/tests/test_belief_weights.py`, update `test_phase2_constants_present`:

```python
def test_phase2_constants_present():
    from science_tool.graph import belief_weights as bw
    assert bw.PROXY_STEP_PENALTY == 2
    assert bw.CURATION_STEP_PENALTY == 1
    assert bw.DELTA_ENVELOPE == (0.3, 1.0)
    assert bw.CONFIG_VERSION == "belief-logodds-v2"
```

Also update the two other `belief-logodds-v1` literals so the bump stays atomic (the whole suite is green at this commit, not just `test_belief_weights`):
- `science/tests/test_belief_snapshot.py:42` — `assert row["config_version"] == "belief-logodds-v1"` → `"belief-logodds-v2"`.
- `science/tests/test_belief_cli.py:20` — the fixture literal `"config_version": "belief-logodds-v1",` → `"belief-logodds-v2",`.

(These are the only two remaining `belief-logodds-v1` literals besides `belief_weights.py` and `test_belief_weights.py`; Task 5 Step 2 re-greps as a safety net, but they belong in this commit.)

In `science/tests/test_belief_reduce.py` (READ it first to match how it builds `EvidenceUnit`s and calls `reduce_units`/`quality_key`). Add a test that, within one independence group and stance, an otherwise-equal **non-reference** unit beats a **reference** one:

```python
def test_reference_unit_loses_winner_selection_tiebreak():
    # Two support units, same group, IDENTICAL type/role/strength; one rests on a reference dataset.
    ref = <build EvidenceUnit ... is_reference_dataset=True, independence_group="g", line_uri="r">
    nonref = <build EvidenceUnit ... is_reference_dataset=False, independence_group="g", line_uri="n">
    reduced = reduce_units([ref, nonref])
    kept_uris = {u.line_uri for u in reduced.kept}
    assert kept_uris == {"n"}                       # non-reference kept on the exact tie
    assert any(u.line_uri == "r" for u in reduced.collapsed)


def test_reference_penalty_is_tiebreaker_only_not_cross_tier():
    # Locks the deviation: the curation demotion is the LEAST-significant component, so a
    # reference unit that is strictly stronger on a higher tier (here strength) STILL wins —
    # the penalty never crosses type/role/strength.
    strong_ref = <build EvidenceUnit ... strength="strong", is_reference_dataset=True,
                  independence_group="g", line_uri="r">
    weak_nonref = <build EvidenceUnit ... strength="moderate", is_reference_dataset=False,
                   independence_group="g", line_uri="n">
    reduced = reduce_units([strong_ref, weak_nonref])
    assert {u.line_uri for u in reduced.kept} == {"r"}   # stronger reference unit still wins
```

- [ ] **Step 2: Run to verify failure**

```bash
cd ~/d/science/science && uv run pytest tests/test_belief_scalar.py tests/test_belief_weights.py tests/test_belief_reduce.py -q -k "reference or curation or constants_present"
```
Expected: FAIL (no `CURATION_STEP_PENALTY`; `unit_score` ignores the flag; `CONFIG_VERSION` still `-v1`).

- [ ] **Step 3: Add the constant + bump the version**

In `science/src/science_tool/graph/belief_weights.py`, edit the constants block:
```python
PROXY_STEP_PENALTY = 2          # gated proxy counts two ordinal steps lower (logic, not a cliff)
CURATION_STEP_PENALTY = 1       # reference (human-curated) dataset: one ordinal step lower (A2/A-D4)
DELTA_ENVELOPE = (0.3, 1.0)     # log-odds per ordinal step; OR ~1.35..2.72; SWEPT, not chosen
CONFIG_VERSION = "belief-logodds-v2"   # A2 curation down-weight; bump on any change here
```

- [ ] **Step 4: Apply in `unit_score` (scalar path)**

In `science/src/science_tool/graph/belief_scalar.py`, extend the `belief_weights` import and `unit_score`:
```python
from .belief_weights import (
    CURATION_STEP_PENALTY, DELTA_ENVELOPE, PROXY_STEP_PENALTY,
    role_steps, strength_steps, type_steps,
)


def unit_score(u: EvidenceUnit) -> int:
    s = type_steps(u.evidence_type) + role_steps(u.evidence_role) + strength_steps(u.strength)
    if is_proxy_gated(u):
        s = max(0, s - PROXY_STEP_PENALTY)
    if u.is_reference_dataset:
        s = max(0, s - CURATION_STEP_PENALTY)
    return s
```

- [ ] **Step 5: Apply in `quality_key` (winner-selection path)**

In `science/src/science_tool/graph/belief.py`, add `CURATION_STEP_PENALTY` to the `belief_weights` import block, then extend `quality_key` with a least-significant demotion component:
```python
def quality_key(u: EvidenceUnit) -> tuple[int, int, int, int]:
    # A-D4: the curation discount also routes through winner-selection. It is the LAST
    # (least-significant) component, so a reference-backed unit loses only to an otherwise
    # equal (type/role/strength) non-reference unit — it never crosses those axes.
    return (
        EVIDENCE_TYPE_RANK.get(normalize_evidence_type(u.evidence_type), 0),
        EVIDENCE_ROLE_RANK.get(u.evidence_role or "", 0),
        STRENGTH_RANK.get(u.strength or "", 0),
        -CURATION_STEP_PENALTY if u.is_reference_dataset else 0,
    )
```

- [ ] **Step 6: Run to verify PASS**

```bash
cd ~/d/science/science && uv run pytest tests/test_belief_scalar.py tests/test_belief_weights.py tests/test_belief_reduce.py tests/test_belief_aggregate.py tests/test_belief_classify.py tests/test_belief_refutation.py tests/test_belief_snapshot.py tests/test_belief_cli.py -q
```
Expected: PASS (including the snapshot/CLI files whose v1 literals you just bumped). Pre-existing scalar/reduce tests use non-reference units (`is_reference_dataset` defaults `False`), so their scores/winners are unchanged.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/graph/belief_weights.py science/src/science_tool/graph/belief_scalar.py science/src/science_tool/graph/belief.py science/tests/test_belief_scalar.py science/tests/test_belief_weights.py science/tests/test_belief_reduce.py science/tests/test_belief_snapshot.py science/tests/test_belief_cli.py
git commit -m "feat(belief): curation down-weight for reference datasets + config v2 (A2)"
```

---

## Task 4: `identification_strength: structural` recording nudge (validate, no scoring)

A soft `science validate` WARN: when an evidence line rests on a `reference` dataset but declares no `identification_strength`, nudge the author to consider `structural` (A-D4 reference-as-basis). This is **recording only** — it does not affect scores.

**Files:**
- Modify: `science/src/science_tool/validate/checks/evidence_lines.py` (add a graph-based check, mirroring the existing belief checks there that load `knowledge`/`provenance`)
- Test: the evidence-lines validate-check test file (match the existing one, e.g. `science/tests/validate/test_checks_evidence_lines*.py`)

- [ ] **Step 1: Read the existing idiom**

READ `science/src/science_tool/validate/checks/evidence_lines.py` to see how its graph-based checks (a) load `knowledge`/`provenance` (the `_load_*` helper returning the two graphs), (b) iterate evidence-line URIs (`rdf:type sci:EvidenceLine`), (c) read per-line predicates from `provenance`, and (d) are registered with `@Check(section=…, order=…)`. Match that idiom exactly; do not invent a new check module.

- [ ] **Step 2: Write the failing test**

In the matching test file, add (adapt the harness to how that file stands up a graph/project — reuse its existing fixture):

```python
def test_reference_basis_without_identification_strength_warns(<harness args>):
    # Project graph with: an evidence line (rdf:type EvidenceLine, cito:supports a claim),
    #   its source dataset carrying sci:sourceClass "reference",
    #   and NO sci:identificationStrength on the line.
    rules = <run the evidence-lines checks and collect (severity, rule)>
    assert (Severity.WARN, "evidence.reference-basis-no-identification-strength") in rules


def test_reference_basis_with_identification_strength_is_silent(<harness args>):
    # Same, but the line declares sci:identificationStrength "structural".
    rules = <...>
    assert "evidence.reference-basis-no-identification-strength" not in [r for _, r in rules]


def test_non_reference_source_does_not_nudge(<harness args>):
    # Source dataset is observational → no nudge regardless of identification_strength.
    rules = <...>
    assert "evidence.reference-basis-no-identification-strength" not in [r for _, r in rules]
```

- [ ] **Step 3: Run to verify failure**

```bash
cd ~/d/science/science && uv run pytest <evidence-lines test file> -q -k reference_basis
```
Expected: FAIL (the rule is not emitted).

- [ ] **Step 4: Add the check**

Add a new `@Check`-decorated function in `evidence_lines.py` (reuse its graph-loading helper). **`order` is a GLOBAL sort key across all check modules, not per-module** — the A1 lesson (the plan's first guess of 29 was globally taken). Orders 23–31 are currently occupied (31 is A1's `dataset_taxonomy`), so use **`order=32`**. Confirm it is still free before using:
```bash
cd ~/d/science/science && grep -rhoE "order=[0-9]+" src/science_tool/validate/checks/ | sort -u
```
If 32 is taken, use the next free integer and report it. Logic:

```python
# inside the new check, with `knowledge`, `provenance` already loaded by the module's helper:
reference_uris = {str(s) for s, _, _ in knowledge.triples((None, SCI_NS.sourceClass, Literal("reference")))}
for line in <evidence-line URIs in knowledge>:
    derived = {str(o) for _, _, o in provenance.triples((line, PROV.wasDerivedFrom, None))}
    if not (derived & reference_uris):
        continue
    if any(provenance.triples((line, SCI_NS.identificationStrength, None))):
        continue
    yield Result(
        Severity.WARN, <line source path or None>, None,
        f"{<line id/uri>}: evidence rests on a reference dataset but declares no "
        f"identification_strength; if the curated set IS the basis of the claim, "
        f"set identification_strength: structural (A2/A-D4)",
        "evidence.reference-basis-no-identification-strength", None,
    )
```

Use whatever `SCI_NS`/`Literal`/`PROV` imports and `Result`/`Severity` constructor the module already uses. The check must be **tolerant** (no graph / no datasets ⇒ no results), consistent with the other checks in the file.

- [ ] **Step 5: Run to verify PASS**

```bash
cd ~/d/science/science && uv run pytest <evidence-lines test file> -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/evidence_lines.py <evidence-lines test file>
git commit -m "feat(validate): nudge identification_strength=structural for reference-basis lines (A2)"
```

---

## Task 5: Full regression + config re-baseline note + docs

**Files:**
- Modify: `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` (§8 status, §9)
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` (§6 table A row, §8)

- [ ] **Step 1: Full regression**

```bash
cd ~/d/science/science && uv run pytest model/tests/ tests/ -q
```
Expected: PASS. The `CONFIG_VERSION` bump only affects the constant assertion (updated in Task 3) and the belief-snapshot reproducibility check, which silently stops matching old-version rows — it does **not** error. Confirm `tests/test_belief_snapshot.py` passes (its in-memory units are non-reference, so `massed_support_score` is unchanged; only the embedded `config_version` string changes — update any literal `belief-logodds-v1` assertion in that file to `-v2` if present). Investigate any failure before proceeding; do **not** edit tests merely to pass.

- [ ] **Step 2: Confirm no in-repo golden snapshot files encode v1**

```bash
cd ~/d/science/science && grep -rn "belief-logodds-v1" tests src || echo "no v1 literals remain"
```
Expected: no remaining `belief-logodds-v1` literals (the combined validate fixture carries no `belief-snapshots.jsonl`, so the CLI output snapshots under `tests/validate/snapshots/` are unaffected). If any remain, fix the source/test that owns them.

- [ ] **Step 3: Update the Pillar A design (§8 + §9)**

In `docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md`: change the §8 A2 row status to **merged**, and update §9 + the top `Status:` line to record A2 implemented: curation down-weight (`CURATION_STEP_PENALTY = 1`, one ordinal score step floored at 0) applied as the full step in `unit_score` (the scalar/log-odds path) and as a **tiebreaker-only demotion in Phase 1 winner-selection** (`quality_key`) — state explicitly that A-D4's "route through both paths" is realized as the full step in the scalar and a least-significant tiebreaker in Phase-1 `reduce_units` (it does not demote across the lexicographic `type/role/strength` tiers; a true cross-tier penalty would require flattening `quality_key` to a summed-step scalar and is out of A2 scope). Also record: `source_class` materialized as `sci:sourceClass` and threaded to `EvidenceUnit.is_reference_dataset`; `CONFIG_VERSION` bumped to `belief-logodds-v2`; `identification_strength: structural` shipped as a **recording-only validate nudge** (not wired into scoring); per-line override deferred. Use `~/d/` for any paths.

- [ ] **Step 4: Update the umbrella (§6 + §8)**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`: update the §6 Phase-2 (A) row to "impl: **A1 + A2 merged** (recording layer + curation down-weight, config v2); Pillar A complete", and update the §8 Pillar-A paragraph and the "Remaining" sentence accordingly (A no longer gates D/B on A2). Mirror the existing C/A1 annotation style.

- [ ] **Step 5: Commit**

```bash
git add docs/plans/historical/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
git commit -m "docs(bio): mark A2 (curation down-weight) merged"
```

---

## Self-review checklist (run before handing to executor)

- **Spec coverage (A-D4):** curation down-weight = one ordinal step floored at 0 → full step in `unit_score` (Task 3) ✓; routed through **both** paths once each → full step in scalar + **tiebreaker-only demotion in Phase-1 `quality_key`** (Task 3), an explicit documented narrowing recorded in the design (Task 5 Step 3), with tests locking both the exact-tie loss and the strictly-stronger-still-wins (no cross-tier) cases ✓; never mutates stance/strength/evidence_type/independence, no strength cap → only `is_reference_dataset` read, no other field touched ✓; bump config version → `belief-logodds-v2` (Task 3) ✓. `identification_strength: structural` → **recording nudge only** (Task 4, `order=32`), per user decision, not scoring. Per-line override → **deferred**, per user decision.
- **Resolution path:** `sci:sourceClass` materialized into `knowledge` on the dataset URI (Task 1) = the same URI an evidence line's `prov:wasDerivedFrom` resolves to; detection scans **all** derived-from objects, not first-wins (Task 2). Both load paths (markdown + datapackage) carry `source_class` from A1, and `_add_entity` reads it backend-agnostically.
- **No double-count:** the penalty is applied once per unit in each path; proxy and curation penalties stack additively and independently (Task 3 test asserts 7−2−1=4), each floored at 0.
- **Type consistency:** `is_reference_dataset: bool` identical across `EvidenceUnit` def, `_read_unit`, and both scoring readers; `CURATION_STEP_PENALTY` referenced in `belief_weights`, `belief_scalar`, `belief`. `quality_key` return type widened 3-tuple → 4-tuple; its only consumer is `reduce_units`.
- **Backward-compat:** new `EvidenceUnit` field is defaulted + last, so existing keyword constructions in `test_belief_*` keep working; `collect_evidence_units` caller signatures unchanged.
- **Config bump atomicity + blast radius:** all in-repo `belief-logodds-v1` literals (`belief_weights.py`, `test_belief_weights.py`, `test_belief_snapshot.py:42`, `test_belief_cli.py:20`) are updated in the **same commit** as the bump (Task 3), so the suite is green at that commit; Task 5 Step 2 re-greps as a safety net. Downstream `belief-snapshots.jsonl` re-baseline is expected and non-erroring (the reproducibility check silently stops matching old-version rows).
- **No placeholders in production code:** every production step has exact code. Test steps for graph/validate harnesses (Tasks 1/2/4) give exact assertions + the triples to build, with an explicit "match the existing fixture" instruction where the harness shape is file-specific.
- **Scope discipline:** no new belief levels, no new aggregation pass, no `identification_strength` scoring, no per-line override. A2 feeds the existing machinery.
