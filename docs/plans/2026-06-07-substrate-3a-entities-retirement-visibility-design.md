# Substrate Phase 3a — `entities.yaml` retirement: visibility & inventory (design)

> **Status:** approved design, pre-implementation. Feeds the writing-plans step.
> **Series:** substrate redesign, Part B/C of
> `2026-06-06-knowledge-meta-model-and-substrate-design.md` (§B5, §C2, §C3).
> **Predecessors merged:** Phase 1 (compiler seam) · 2a/2b/2c (dataset
> reconciliation). Phase 3 is decomposed into **3a (this doc) → 3b → 3c**; only
> 3a is specified here.

## 1. Why this exists (reconciling §B5 with reality)

The master design's §B5 describes `entities.yaml` as sole-sourcing **fileless**
`concept`/`decision`/`latent` kinds, with everything else being stub-shadows of
real markdown owners. The only live aggregate file in the repo set
(`~/d/.../multiple-myeloma/knowledge/sources/local/entities.yaml`, 176 entries)
is materially messier. Using each entry's inner `source_path` as the
discriminator:

| Observed group | Count | §B5 disposition |
|---|---|---|
| `article`, self-sourced | 76 | external references (bibliographic) — **blocked on Phase 4** authority resolver |
| `concept`/`latent`, self-sourced | 26 | coined-here → owner files (canonical §B5 case) |
| `decision` from `core/decisions.md` | 16 | owner files **+** `decisions.md` becomes a generated view (3c) |
| `paper`/`topic` shadowing a real `.md` | 18 | stub-shadows → delete |
| `migration:audit` / `migration:synth` | 26 | degenerate audit-injected stubs — **not in the §B5 model at all** |
| `question`/`topic`, self-sourced | 14 | ambiguous — human call |

Three facts reshape the scope and force a decomposition:

1. **The target project is still `layout_version: 2`.** There is no `entities/`
   directory; markdown owners live in `doc/papers/`, `specs/hypotheses/`,
   `specs/propositions/`, etc. §B5 presumes the markdown kinds already migrated
   to `entities/<kind>/`. Phase 3 therefore builds **science-framework tooling
   validated on fixtures**, not a content migration of any real project. Running
   it against MM30 is gated on the still-pending v2→v3 markdown migration
   (project Task #30).
2. **The largest bucket (76 `article` → external refs) is blocked on Phase 4**
   (the authority resolver; master design §D4 — external refs are "recognized
   but not richly resolved" until the bio identity pillar lands). *Full*
   retirement of an `entities.yaml` cannot complete within Phase 3.
3. **26 entries are `migration:*` audit cruft** the §B5 model never anticipated.
   The triage taxonomy needs an explicit bucket for them.

Because §B5 bundles several independent subsystems (triage classifier · `--apply`
promote/delete · `decisions.md` generator · `AggregateAdapter` removal +
lone-stub visibility · external-ref handling) and parts are blocked, Phase 3 is
sliced. **3a is the non-destructive visibility slice** — the smallest,
fully-unblocked first step, matching the 2a→2b→2c rhythm.

## 2. Scope

### In scope (3a)

1. A standing **lone-aggregate-stub conformance check** (WARN, unconditional).
2. A **read-only triage classifier + report** that buckets every aggregate row
   with per-row evidence.

Both are pure science-framework changes, fixture-tested, with **no file
creation, no deletion, no `--apply`**.

### Out of scope (deferred)

| Deferred item | Phase |
|---|---|
| `--apply`: promote `coined`/`decision-log` → owner files; delete confirmed `shadow`/`cruft` | 3b |
| `core/decisions.md` as a generated view over `entities/decision/*.md` | 3c |
| Remove the `AggregateAdapter` deprecated-owner mode (gated on zero aggregate rows remaining) | 3c |
| External-reference resolution for the `article` bucket | Phase 4 |
| Running any retirement against MM30 content | after MM30 reaches v3 (Task #30) |

## 3. Architecture

### 3.1 The §C2 law

Both deliverables **read the compiled model** — the `IdentityTable` and the
`Entity` set produced by `load_project_sources` — and never re-walk
`entities.yaml`. Grounding facts (verified against the code):

- `AggregateAdapter.name == "aggregate"`; `classify_owner_scope("aggregate")`
  yields a deprecated owner. So aggregate rows appear in the identity table as
  `IdentityDeclaration` rows with `adapter == "aggregate"` and
  `deprecated == True`.
- `AggregateAdapter.load_raw` preserves each entry's inner fields on the
  compiled `Entity` — including `source_path` (e.g. `core/decisions.md`,
  `migration:audit`, `papers/references.bib`, or the aggregate file itself when
  self-sourced) and `kind` (else derived from the `canonical_id` prefix).
- "Is there a real (non-aggregate) owner of this id?" is answered from the
  identity table: an `IdentityDeclaration` for the same `(owner_scope,
  canonical_id)` whose `adapter != "aggregate"` and `deprecated == False`.

### 3.2 Single-surface split

To avoid two surfaces reporting one condition (the principle Phase 2b
established by routing `identity_collision` to a single check):

- The **check** is the standing `validate` gate, and it fires **only on lone
  stubs** — an aggregate owner row with no co-owner of the same id. A *shadowed*
  aggregate stub (a real owner exists) is already surfaced as WARN by
  `forbidden-second-declaration` (2b); the new check skips it.
- The **report** is richer and orthogonal: it buckets **all** aggregate rows
  (lone and shadowed) for human triage. It is decision-support for 3b, not a
  gate.

## 4. Component 1 — lone-aggregate-stub check

**File:** `src/science_tool/validate/checks/aggregate_stub.py` (new), registered
in the canonical-check tuple.

**Behavior:**

- Load the project non-strict, no commons (matching the orphan and
  collision checks): a diagnostic must not abort on the condition it reports.
- Build the identity table. For each `adapter == "aggregate"`,
  `deprecated == True` owner row that is **lone** (no other owner row shares its
  `(owner_scope, canonical_id)` key), emit one `Result`.
- **Severity: WARN, unconditional** (independent of `layout_version`). Rationale:
  the fix tool (3b `--apply`) does not exist yet, so an ERROR would mark debt a
  project cannot clear this phase (master design §C4 — "a half-rolled project is
  never bricked"). Flipping to ERROR-at-v3 is explicitly revisited in 3b/3c once
  the retirement path exists.
- Rule id: `lone-aggregate-stub`. Message names the canonical id and points at
  the (future) triage report / 3b retirement path, and at this design doc.

**Lone vs. shadowed determination** reuses the existing
`IdentityCollision.is_genuine` / `table.collisions()` machinery only to *exclude*
collided ids; a lone stub is one whose id is **not** in any collision. (A
shadowed stub *is* in a collision and is handled by `forbidden-second-declaration`.)

**Registration test:** the real wiring pattern from 2b — `clear_checks_for_tests`
→ `sys.modules.pop` the module → `_load_canonical_checks()` → assert the
`@Check` ran and is in `CANONICAL_CHECKS` with the expected order. Importing the
check at module top would register it even if the tuple entry were missing, so
the test proves the tuple entry, not the import.

## 5. Component 2 — triage classifier + report

### 5.1 Pure classifier

**File:** `src/science_tool/graph/aggregate_triage.py` (new).

```
class AggregateBucket(StrEnum):
    SHADOW = "shadow"
    COINED = "coined"
    DECISION_LOG = "decision-log"
    EXTERNAL_REF = "external-ref"
    CRUFT = "cruft"
    AMBIGUOUS = "ambiguous"

@dataclass(frozen=True, slots=True)
class AggregateRowTriage:
    canonical_id: str
    kind: str
    source_path: str
    has_real_owner: bool
    bucket: AggregateBucket
    evidence: str          # one-line, human-readable basis for the bucket

def classify_aggregate_rows(sources: ProjectSources) -> list[AggregateRowTriage]:
    ...
```

The function consumes `ProjectSources` (the compiled model). It pairs each
`adapter == "aggregate"` owner declaration with its `Entity` (for `source_path`
and `kind`), computes `has_real_owner` from the identity table, applies the
deterministic rules below, and returns one triage row per aggregate declaration,
sorted by `(bucket, canonical_id)` for stable output.

### 5.2 Deterministic bucket rules

Applied in order; first match wins. `agg_path` is the aggregate file's own path
(self-sourced ⇔ `source_path == agg_path` or `source_path` is empty/absent).

1. **`shadow`** — `has_real_owner` is true (a non-aggregate, non-deprecated owner
   of the same id exists). *Disposition (3b): delete the stub.*
2. **`cruft`** — `source_path` starts with `migration:`. *Disposition (3b):
   delete / hand-triage.*
3. **`decision-log`** — `kind == "decision"` and `source_path == "core/decisions.md"`.
   *Disposition (3b owner file + 3c generated view).*
4. **`external-ref`** — `kind == "article"`, or `source_path` ends with `.bib`.
   *Disposition (Phase 4): resolve as an external reference, no file.*
5. **`coined`** — self-sourced and `kind in {concept, latent}` (or a `decision`
   not sourced from the decisions log), and not shadowed. *Disposition (3b):
   promote to an owner file.*
6. **`ambiguous`** — anything else (e.g. self-sourced `question`/`topic`).
   *Disposition: human call; no automated action proposed.*

The rules are **heuristics with surfaced evidence**, not authoritative
judgments — master design §D5 flags the concept-vs-tag boundary as judgment, not
algorithm. The report exists so a human reviews and overrides before 3b acts.
The `evidence` string records the matched basis (e.g. `"kind=article →
external-ref"`, `"real owner at doc/papers/foo.md → shadow"`).

### 5.3 CLI report

**Command:** `science entities triage-aggregate` (read-only in 3a; 3b adds
`--apply`). Lives in the existing `entities` group alongside `inventory` /
`migrate`.

- `--project-root <path>` (default `.`).
- Default text output: a per-bucket count summary, then a per-row table
  (`bucket`, `canonical_id`, `kind`, `source_path`, `evidence`).
- `--format json`: emit the `AggregateRowTriage` list as JSON for machine use.
- Exit code 0 always (a report, not a gate). The standing gate is Component 1.

## 6. Testing

`cd ~/d/science/science && uv run --frozen pytest`; lint with
`uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char).

- **Classifier unit tests** (`tests/graph/test_aggregate_triage.py`): a fixture
  project whose `entities.yaml` carries at least one row per bucket, plus a
  shadowed-vs-lone pair; assert each row's `bucket` and `has_real_owner`. Cover
  rule precedence (e.g. a `migration:`-sourced row that is also shadowed lands in
  `shadow`, since rule 1 precedes rule 2 — and assert that ordering deliberately).
- **Check tests** (`tests/validate/test_checks_aggregate_stub.py`): a lone stub
  WARNs; a shadowed stub does **not** WARN here (it is the collision check's
  surface); two real owners are untouched; the registration wiring test.
- **CLI tests** (`tests/test_cli_*` peer): smoke the text report and assert the
  `--format json` shape and per-bucket counts on the fixture.

The deprecated `entities.yaml` aggregate stub only loads under a
`profiles: {local: local}` manifest (the aggregate scan root), **not**
`knowledge_profiles:` — fixtures must use the `profiles:` manifest style (the 2b
gotcha).

## 7. Risks & mitigations

- **Heuristic misclassification.** Mitigated by read-only output + surfaced
  evidence; no irreversible action in 3a. 3b's `--apply` will require explicit
  per-bucket opt-in and re-run the classifier on live state.
- **Double-surfacing the same debt.** Mitigated by the single-surface split
  (§3.2): the check fires only on lone stubs; shadows stay with the collision
  check.
- **Drift from the real `AggregateAdapter` contract.** Mitigated by consuming the
  compiled model (`adapter == "aggregate"`, `Entity.source_path`) rather than
  re-parsing YAML, so the report tracks whatever the adapter actually emits.

## 8. Success criteria

- `science validate` WARNs each lone aggregate stub (and nothing more from this
  check), unconditionally.
- `science entities triage-aggregate` buckets all aggregate rows with evidence,
  in text and JSON, read-only, exit 0.
- No content is created, deleted, or mutated by any 3a code path.
- Full suite green; ruff clean on changed files.
