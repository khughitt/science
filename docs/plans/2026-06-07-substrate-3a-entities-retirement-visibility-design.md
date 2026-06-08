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

1. An additive **loader change** surfacing aggregate row-level metadata
   (`ProjectSources.aggregate_rows`, §3.1) — the prerequisite that makes the
   `shadow` and `source_path` buckets computable from the compiled model.
2. A standing **lone-aggregate-stub conformance check** (WARN, unconditional).
3. A **read-only triage classifier + report** that buckets every aggregate row
   with per-row evidence.

All three are pure science-framework changes, fixture-tested, with **no file
creation, no deletion, no `--apply`**, and no mutation of any entity or content.

### Out of scope (deferred)

| Deferred item | Phase |
|---|---|
| `--apply`: promote `coined`/`decision-log` → owner files; delete confirmed `shadow`/`cruft` | 3b |
| `core/decisions.md` as a generated view over `entities/decision/*.md` | 3c |
| Remove the `AggregateAdapter` deprecated-owner mode (gated on zero aggregate rows remaining) | 3c |
| External-reference resolution for the `article` bucket | Phase 4 |
| Running any retirement against MM30 content | after MM30 reaches v3 (Task #30) |

## 3. Architecture

### 3.1 The §C2 law and the row-metadata prerequisite

Both deliverables **read the compiled model** — the `IdentityTable` plus a new
row-level metadata map, both produced by `load_project_sources` — and never
re-walk `entities.yaml`. Grounding facts (verified against the code):

- `AggregateAdapter.name == "aggregate"`; `classify_owner_scope("aggregate")`
  yields a deprecated owner. Each aggregate entry appears in the identity table
  as an `IdentityDeclaration` with `adapter == "aggregate"`,
  `deprecated == True`, and a `source_ref` carrying the entry's `(path, line)`.
- **The aggregate `Entity` is *not* a reliable carrier** (this is the correction
  to the first draft). Under the non-strict load diagnostics use, a *shadowed*
  aggregate row's `IdentityDeclaration` is appended (`sources.py:406`) but its
  `Entity` is then skipped by the dedup guard (`sources.py:416-420`, the
  `continue`) because a real owner already won the id — i.e. exactly the
  `shadow` bucket has no aggregate `Entity`. Separately, `AggregateAdapter.load_raw`
  records the aggregate *file* as `Entity.file_path`; the entry's inner
  `source_path` is **not** surfaced as an `Entity` field. So neither
  `has_real_owner` nor `source_path` can be read off the aggregate `Entity`.
- **Prerequisite loader change (additive, non-destructive).** At the
  aggregate-declaration emit point (`sources.py:~406`, where `raw` and `kind` are
  still in scope), capture the entry's triage metadata into a new field
  `ProjectSources.aggregate_rows: dict[tuple[str, int], AggregateRowMeta]` keyed
  by `(source_ref.path, source_ref.line)` — carrying `kind` and the inner
  `source_path`. `source_path` is unschema'd extra metadata, so a malformed
  (non-string) value is **normalized to `None` at capture**
  (`sp = raw.get("source_path"); sp if isinstance(sp, str) else None`) — a
  read-only visibility tool must never crash on a bad row. This records metadata
  for **both** lone and shadowed rows, *before* the dedup-skip, with no second
  disk read and no entity mutation. New dataclass (e.g. in `graph/sources.py`
  beside `ProjectSources`):

  ```python
  @dataclass(frozen=True, slots=True)
  class AggregateRowMeta:
      kind: str
      source_path: str | None  # entry's inner source_path; None when absent or non-string
  ```

- `has_real_owner` is computed from the **identity table alone**: for an
  aggregate declaration's `(owner_scope, canonical_id)`, does another
  declaration exist with `adapter != "aggregate"` and `deprecated == False`? No
  `Entity` is consulted.
- **Self-sourced** ⇔ the entry's `source_path` is `None`/absent, the **empty
  string**, **or** equals the declaration's own `source_ref.path` (the aggregate
  file). In MM30 the self-sourced rows carry
  `source_path: knowledge/sources/local/entities.yaml` (the aggregate file itself).

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

**File:** `src/science_tool/validate/checks/aggregate_stub.py` (new). Registered
in `CANONICAL_CHECK_MODULES` (`validate/checks/__init__.py`) in the tuple slot
**immediately after `"identity_collision"`** (keeping the substrate-identity
checks adjacent), and decorated `@Check(section=..., order=51)` — sequencing
right after `identity_collision` (order 50; `orphan_datapackage_owner` is 49).

**Behavior:**

- Load the project with `include_commons=False, strict_identity=False,
  strict_core_schema=False` (matching `check_forbidden_second_declaration`,
  `identity_collision.py:56`): a diagnostic must not abort on the condition it
  reports, and `strict_core_schema=False` keeps a malformed aggregate/core row
  from crashing the visibility tool before it can report.
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
`@Check` ran and is in `CANONICAL_CHECKS` with `order == 51`. Importing the
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

The function consumes `ProjectSources` (the compiled model). For each
`adapter == "aggregate"` owner declaration it looks up
`sources.aggregate_rows[(decl.source_ref.path, decl.source_ref.line)]` for
`kind` and `source_path` (per §3.1 — **not** the aggregate `Entity`, which is
absent for shadows), computes `has_real_owner` from the identity table, applies
the deterministic rules below, and returns one triage row per aggregate
declaration, sorted by `(bucket, canonical_id)` for stable output. The caller
builds the identity table via `build_identity_table(sources)` and loads with the
same `include_commons=False, strict_identity=False, strict_core_schema=False`
flags as the check (§4).

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

- **Classifier tests** (`tests/graph/test_aggregate_triage.py`): the full
  six-bucket matrix + precedence is unit-tested on the pure `_bucket` helper
  (e.g. a `migration:`-sourced row that is also shadowed lands in `shadow`, rule 1
  before rule 2) — this avoids the loader, since `decision`/`latent` are local
  (not core) kinds the synthetic loader would skip. Separate **integration**
  tests drive `load_project_sources → classify_aggregate_rows` with core kinds
  only (`concept`→coined, `dataset`+markdown owner→shadow, `article`→external-ref
  keyed by the canonicalized `paper:` id), plus an empty-`source_path`→self-sourced
  case and a non-string-`source_path`→`None` case.
- **Check tests** (`tests/validate/test_checks_aggregate_stub.py`): a lone stub
  WARNs; a shadowed stub does **not** WARN here (it is the collision check's
  surface); two real owners are untouched; the registration wiring test.
- **CLI tests** (`tests/test_cli_*` peer): smoke the text report and assert the
  `--format json` shape and per-bucket counts on the fixture.

**Fixture gotcha (corrected).** `AggregateAdapter` scans
`knowledge/sources/<local_profile>/`, where `<local_profile>` is the profile
map's **value**. So the entry's *value* must map to the directory where
`entities.yaml` actually lives — e.g. `knowledge_profiles: {local: local}` →
`knowledge/sources/local/entities.yaml`. The key (`knowledge_profiles:`,
preferred, vs legacy `profiles:`) does **not** matter; both resolve the same way
(`_read_project_config` prefers `knowledge_profiles`, falls back to `profiles`).
The earlier "must use `profiles:`" framing was a misattribution: the 2b general
fixture failed to discover the stub because its value was `knowledge/local`
(→ nonexistent `knowledge/sources/knowledge/local/`), not because of the key.
Reuse the proven 2b pattern (`_AGG_MANIFEST` + `_write_aggregate_stub` in
`tests/validate/test_checks_identity_collision.py`).

## 7. Risks & mitigations

- **Heuristic misclassification.** Mitigated by read-only output + surfaced
  evidence; no irreversible action in 3a. 3b's `--apply` will require explicit
  per-bucket opt-in and re-run the classifier on live state.
- **Double-surfacing the same debt.** Mitigated by the single-surface split
  (§3.2): the check fires only on lone stubs; shadows stay with the collision
  check.
- **Drift from the real `AggregateAdapter` contract.** Mitigated by capturing the
  row metadata at the loader's emit point (`adapter == "aggregate"`, from the same
  `raw` the adapter built) rather than re-parsing YAML in the classifier, so the
  report tracks whatever the adapter actually emits.
- **`source_ref.line` is load-bearing for the join key.** The metadata map is
  keyed by `(source_ref.path, source_ref.line)`; `AggregateAdapter` always sets
  `line` (the entry index, asserted in `load_raw`), so the key is total over
  aggregate rows. Non-aggregate adapters never populate `aggregate_rows`, so the
  classifier only ever joins keys it wrote.

## 8. Success criteria

- `science validate` WARNs each lone aggregate stub (and nothing more from this
  check), unconditionally.
- `science entities triage-aggregate` buckets all aggregate rows with evidence,
  in text and JSON, read-only, exit 0.
- No content is created, deleted, or mutated by any 3a code path.
- Full suite green; ruff clean on changed files.
