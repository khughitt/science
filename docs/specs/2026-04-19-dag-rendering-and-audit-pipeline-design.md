# DAG Rendering and Audit Pipeline — Design

**Date:** 2026-04-19
**Status:** proposed
**Source:** mm30 `discussion:2026-04-19-dag-iteration-and-refinement` (Phase 1 + Phase 3 lift)
**Depends on:**
- `2026-03-07-phase4b-causal-dag-design.md` (approved)
- `2026-04-17-edge-status-dashboard-design.md` (proposed)
- `2026-04-17-inquiry-edge-posterior-annotations-design.md` (proposed)

**Amends:** `2026-04-17-edge-status-dashboard-design.md` (adds `eliminated` to the enum; graph storage for the new enum value and for the `identification` axis is explicitly deferred to Phase 2 `sync-dag` — see §"Schema extensions").

## Goal

Lift mm30's **evidence-curated DAG rendering + audit machinery** into
`science-tool` so any `research`-profile project gets:

1. YAML-driven visual DAG rendering with honest two-axis evidence encoding
   (replication strength × identification strength).
2. Provenance-preserving retraction (`eliminated` status) for claims
   overturned by subsequent evidence.
3. A staleness audit that surfaces drift between cited tasks and
   not-yet-propagated new evidence.
4. A scheduled `/science:dag-audit` skill that turns episodic
   maintenance into a deterministic cadence.

Scope covers Phase 1 (lift as-is) + Phase 3 (skill + cadence). Phase 2
(JSON-schema validation) and Phase 4 (visual extensions) are out of
scope and tracked as follow-ups.

## Non-Goals

- Replacing the `graph/causal` triples as source of truth. The rendering
  pipeline treats `.edges.yaml` as a **project-local materialization
  layer**; long-term it can be derived from the graph (see §"Graph vs
  YAML SoT" below).
- Defining a causal-DAG schema de novo. The edge-YAML schema extends
  the existing `edge-status-dashboard` enum and the
  `inquiry-edge-posterior-annotations` posterior block.
- Replacing graphviz. `.dot` remains the topology source; alternative
  renderers (mermaid, d2, pyvis-HTML) are additive.

## Problem

Three proven mm30 workflows currently live only as project-local scripts:

1. `doc/figures/dags/_render_styled.py` (~300 LOC) — reads
   `<slug>.dot` + `<slug>.edges.yaml`, emits `<slug>-auto.dot` and
   `<slug>-auto.png` with two-axis evidence styling. Idempotent.
2. `doc/figures/dags/_number_edges.py` — bidirectional synchronization
   of `.dot` edge IDs with `.edges.yaml` records.
3. `doc/figures/dags/_dag_staleness.py` (new 2026-04-19) — cross-refs
   cited `data_support[].task` IDs against `tasks/done/*.md` +
   `tasks/active.md`, flags stale edges and unpropagated recent tasks.

All three are project-agnostic. The schema they consume (edge_status,
identification, description, data_support, lit_support, posterior,
caveats, eliminated_by) has been pressure-tested on 85 edges across 4
DAGs and three major mid-project reframings (t166, t204, t205).
Keeping them project-local means any second project rebuilds the same
stack from scratch.

## Scope — What Lifts

### Upstream (`science-tool dag` subcommand family)

```
science-tool dag render    [--dag <slug>] [--project <path>]
science-tool dag number    [--dag <slug>] [--force-stubs]
science-tool dag staleness [--stale-days 28] [--recent-days 28] [--json]
science-tool dag audit     [--json]                           # READ-ONLY by default
science-tool dag audit     --fix                              # opens review tasks, proposes YAML edits
science-tool dag init      <slug> --label <LABEL>             # scaffolds .dot + empty edges.yaml
```

`dag render` / `dag number` / `dag staleness` each wrap an
individual script. `dag audit` composes them and is the primary
entry for the `/science:dag-audit` skill.

**Mutation contract (v1, pinned):** `dag render`, `dag number`,
`dag staleness`, and `dag audit` are **read-only by default**.
- `dag render` / `dag number` write to `doc/figures/dags/` only
  (idempotent re-materialization of derived artifacts; no task or
  YAML mutation).
- `dag staleness` is pure reporter; exit 0 = clean; exit 1 = findings
  present. No writes anywhere.
- `dag audit` composes render + staleness; exit code mirrors staleness;
  **does not open tasks or mutate YAML** unless invoked with `--fix`.
- `dag audit --fix` is the only mutation surface: opens review tasks
  for flagged edges, proposes YAML edits for unpropagated tasks, and
  (optionally) commits. The `/science:dag-audit` skill passes `--fix`
  only on explicit user intent.

`--json` is a v1 requirement (not a follow-up) for `dag staleness`
and `dag audit` so the skill and CI have a stable machine-readable
contract.

Path discovery reads from `science.yaml`:

```yaml
dag:
  dag_dir: doc/figures/dags          # default
  tasks_dir: tasks                    # default
  dags:                               # optional whitelist; otherwise auto-discover
    - h1-prognosis
    - h1-h2-bridge
```

If the block is absent, fall back to the `research`-profile defaults.
`software`-profile projects opt in by adding the block explicitly.

### Schema extensions (amends `2026-04-17-edge-status-dashboard-design.md`)

**Scope of the amendment (important).** This spec amends the dashboard
spec's edge-status **enum** (adds `eliminated` as a fifth value) and
introduces the **`identification` sibling axis** at the YAML layer only.
Graph-level storage for both additions — canonical predicates, triple
shapes, `--edge-status-trend` handling, etc. — is **deferred to Phase 2
`sync-dag`**. Phase 1+3 do not write these fields into
`knowledge/graph.trig`; they live only in `<slug>.edges.yaml` and in
the rendering / audit pipeline that reads it.

The edge-status dashboard's existing surface (`--edge-status-distribution`,
`--edge-status-trend`) gains `eliminated` as a visible enum value
automatically if the project feeds its YAML into the graph (via a future
`sync-dag`); until then, `dag render` + `dag audit` report the full
distribution directly from YAML.

**1. Add `eliminated` to the edge_status enum.**

| Status | Meaning |
|---|---|
| `supported` | (unchanged) |
| `tentative` | (unchanged) |
| `structural` | (unchanged) |
| `unknown` | (unchanged) |
| **`eliminated` (new)** | Hypothesised mechanism retracted or ruled out by subsequent evidence. Retained for provenance; rendered dotted grey with `[✗]` marker. Optional `eliminated_by` field lists the closing task / interpretation / discussion IDs. |

Rationale: any longitudinal project accumulates claims that get
overturned. Deleting the edge loses provenance; demoting to `unknown`
conflates "never tested" with "tested and refuted." `eliminated` is
the explicit structural record of "we believed this, we tested it,
we don't believe it anymore."

The dashboard spec's `--edge-status-trend` naturally extends:

```
... -> eliminated     : +2
```

**2. Add an `identification` axis as a sibling of `edge_status`.**

`edge_status` measures *replication strength*; `identification`
measures *causal-identification strength*. These are orthogonal and
should be first-class.

| Level | Meaning |
|---|---|
| `interventional` | Perturbation / KD / OE / inhibitor data identifies the edge |
| `longitudinal` | Within-subject temporal ordering supports directionality |
| `observational` | Cross-sectional regression or correlation; arrow is *assumed*, data is *consistent* with it |
| `structural` | Proxy / definitional / measurement relation |
| `none` | No evidence of any identification type (valid for `unknown` edges) |

The existing edge-status dashboard summary gains a parallel
`--identification-distribution` flag:

```
Identification Distribution
  interventional :  6 ( 7%)
  longitudinal   :  5 ( 6%)
  observational  : 50 (59%)
  structural     : 21 (25%)
  none           :  3 ( 3%)
  TOTAL          : 85
```

The point of the two axes is that they cross-tabulate: "supported AND
observational" (most mm30 edges — strong replication, no intervention)
is honest; "tentative AND interventional" (single weak experiment) is
also honest; both require very different reactions from the reader.

**3. Add optional fields to the edge record.**

```yaml
- id: 6
  source: prc2
  target: ccis
  edge_status: supported
  identification: interventional
  caveats:                                # NEW: list of structured caveats
    - "Perturbation-mechanism-dependent: PRC2-complex loss required; catalytic-only EZH2i insufficient"
  eliminated_by:                          # NEW: only present when edge_status == eliminated
    - task: t204
      description: "Terminal verdict non_adjudicating_under_observational_adjusters (2026-04-18, decision D8)."
  description: |
    ...
  data_support: [...]                     # (existing — per phase4b)
  lit_support: [...]                      # (existing — per phase4b)
  posterior: {...}                        # (existing — per 2026-04-17-inquiry-edge-posterior-annotations)
```

`caveats` is a free-form structured field (list of strings); the
rendering layer optionally surfaces them as edge-label footnotes.
`eliminated_by` is required iff `edge_status == eliminated`; every
entry must resolve via `science-tool refs check` (see §"Reference
schema" below).

**4. Default policy for missing axes.**

- `edge_status` defaults to `unknown` if absent — matches the existing
  edge-status dashboard spec.
- `identification` defaults to **`none`** if absent (NOT `observational`).
  Missing curation is absence of evidence, not a positive claim that
  the edge is observationally supported. Migration projects with
  un-curated edges get `none` + a warning; full validation (reject
  missing) is gated on a future `dag validate --strict` mode once
  migration is complete.
- Defaulting `identification` to `observational` was considered and
  rejected: it would convert missing curation into a positive
  evidentiary claim, which is exactly the failure mode the
  no-fabrication audit discipline is designed to catch.

### Reference schema (for `data_support`, `lit_support`, `eliminated_by`)

All three fields use a **single tagged-ref schema**: each entry has
exactly one "kind" tag (the ref type) plus a required `description`:

```yaml
# Internal project refs (one of):
- task: t204
  description: "..."
- interpretation: 2026-04-18-t204-bulk-composition-beyond-pc-maturity-verdict
  description: "..."
- discussion: 2026-04-19-dag-iteration-and-refinement
  description: "..."
- proposition: p11-t174-t202-rival-model-state
  description: "..."

# Literature refs (one of):
- paper: Ren2019                    # citekey in doc/papers/
  description: "..."
- doi: "10.1038/s41586-024-07328-w"
  description: "..."

# External data refs (one of):
- accession: GSE136410              # GEO/SRA/dbGaP/Synapse
  description: "..."
- dataset: depmap-23q4              # registered dataset id
  description: "..."
```

**Validation rules (v1, fail-fast):**
- Exactly one kind tag per entry. Zero tags or multiple tags → error.
- `description` is required on every entry.
- Internal refs (task / interpretation / discussion / proposition) must
  resolve via `science-tool refs check`:
  - `task:` → exists in `tasks/active.md` or `tasks/done/*.md`.
  - `interpretation:` / `discussion:` → exists in the corresponding
    `doc/` subdirectory.
  - `proposition:` → exists in `specs/propositions/`.
- Literature refs: `paper:` → exists in `doc/papers/`; `doi:` → valid
  DOI syntax (resolution to a paper file is optional, per the
  existing no-fabrication audit pattern).
- External data refs: `accession:` validated against known-registry
  regex; `dataset:` must exist in `datapackage.json` if one is present.

Ref validation errors are fatal for `dag render` and `dag number` in
v1 (they block artifact re-materialization) and are reported but
non-fatal for `dag staleness` (staleness should still surface other
signals even if one edge has a broken ref). `dag audit` aggregates
both.

### Visual encoding (the two-axis rendering contract)

| edge_status | color     | penwidth | style  |
|-------------|-----------|----------|--------|
| supported   | `#2e7d32` | 2.5      | solid  |
| tentative   | `#1565c0` | 1.6      | solid  |
| structural  | `#757575` | 1.0      | solid  |
| unknown     | `#c62828` | 1.2      | dashed |
| eliminated  | `#9e9e9e` | 1.0      | dotted |

**Precedence matrix (explicit, evaluated in order):**

| Priority | Rule | Effect |
|---|---|---|
| 1 (highest) | `edge_status == eliminated` | Force `color = #9e9e9e`, `penwidth = 1.0`, `style = dotted`. Ignore posterior, HDI, and structural-structural rules. A retracted line never implies live support. |
| 2 | `edge_status == structural` **and** `identification == structural` | Force `style = dotted`. |
| 3 | `posterior.beta` present (and not eliminated) | `penwidth = min(4.5, 1.6 + 4·|β|)`. |
| 4 | `posterior.hdi_low ≤ 0 ≤ posterior.hdi_high` (HDI crosses zero, and not eliminated) | Force `style = dashed`. |
| 5 | None of the above | Use STATUS_STYLES defaults for `edge_status`. |

Identification modifiers are applied on top of whatever status-driven
styling survives the precedence matrix:
- `interventional` → double-line color `COLOR:#ffffff:COLOR` (graphviz
  parallel-line syntax).
- `longitudinal` → `arrowhead=vee`.
- Other values → default arrowhead.

Label marker prefixes: `[N]` (edge id), `[✗]` (eliminated),
`[I]` (interventional), `[L]` (longitudinal).

Legend subgraph auto-injected into every `<slug>-auto.png`.

### Staleness audit

```bash
science-tool dag staleness [--recent-days 28] [--json]
```

Reads `tasks/done/*.md` + `tasks/active.md` (frontmatter headers
with `## [tNNN]` + `- completed: YYYY-MM-DD` + `- related: [...]`).
The audit emits **two distinct classes of finding** — these are
different signals and have different actionability, so they are
reported separately:

#### Evidence freshness (drift signal)

An edge is **drifted** if there exists external evidence newer than the
edge's newest cited evidence. Specifically, for each edge:

1. Compute `edge.last_cited_date` = max `completed:` date across the
   edge's `data_support[]` + `eliminated_by[]` entries that resolve to
   a completed task (or `null` if none).
2. Collect `candidate_drift_tasks` = tasks completed **after**
   `edge.last_cited_date` whose `related:` field names (a) the
   hypothesis/inquiry the edge belongs to, OR (b) a proposition cited
   by the edge, OR (c) the edge's `source` or `target` node name.
3. If `candidate_drift_tasks` is non-empty, report the edge with the
   list of candidate tasks.

If an edge carries a `last_reviewed: YYYY-MM-DD` field (optional
manual attestation — "I looked at this edge on this date, no
propagation needed"), use `max(edge.last_cited_date, last_reviewed)`
as the comparison anchor. This is the "manual reset button" for
settled edges where a reviewer has confirmed no update is warranted.

Drift is **NOT** a function of calendar age: a 6-month-old edge with
no new related evidence is not flagged. Conversely, a 2-day-old edge
can be flagged the instant new related evidence lands.

Excludes `eliminated` edges (intentionally frozen).

#### Curation freshness (reviewer attestation signal)

Separate, optional, lower-urgency signal. An edge is **under-reviewed**
if `last_reviewed` is either missing or older than `--recent-days`
(default 28). Reported in a distinct section because the action is
different: "confirm still current" vs "propagate new evidence."

This section is opt-in via `--include-curation-freshness` because
projects that don't use `last_reviewed` attestations would otherwise
see every edge flagged.

#### Structural findings

- **Unresolved cited IDs:** cited task/interpretation/discussion IDs
  that don't resolve via `refs check`. Fail-fast for `dag render` +
  `dag number`; reported-but-non-fatal for `dag staleness` (see
  "Reference schema" §validation rules).
- **Unpropagated recent tasks (orphan side):** tasks completed within
  `--recent-days` whose `related:` field names a DAG-touching entity
  but whose ID is not cited by any edge in any DAG. Complementary to
  the per-edge drift signal: drift is "this edge should be
  reviewed"; orphan is "this task should be cited somewhere."

#### Output contract

- Exit code 0 = no findings; 1 = any finding present.
- Human-readable default output; `--json` emits a stable schema:
  ```json
  {
    "stale_days": null,
    "recent_days": 28,
    "today": "YYYY-MM-DD",
    "drifted_edges": [
      {"dag": "h1-prognosis", "id": 5,
       "source": "prc2", "target": "ifn",
       "last_cited_date": "YYYY-MM-DD",
       "last_reviewed": null,
       "candidate_drift_tasks": [{"id": "tNNN", "completed": "YYYY-MM-DD",
                                  "related": ["hypothesis:h1-..."], "title": "..."}]},
      ...
    ],
    "under_reviewed_edges": [...],
    "unresolved_refs": [...],
    "unpropagated_tasks": [...]
  }
  ```
- `--json` is v1, not a follow-up. The skill and CI both depend on a
  stable contract.

### `/science:dag-audit` skill

New skill under `/mnt/ssd/Dropbox/science/skills/dag-audit.md`:

```
---
name: dag-audit
description: Audit causal DAG freshness — run staleness check, re-render
  all DAG figures, and surface edges that need review. Use on a
  4-weekly cadence or after any major verdict interpretation.
---
```

Workflow:
1. Run `science-tool dag audit --json` — read-only structured report.
2. Present the four finding classes separately:
   - **Drifted edges** (evidence freshness) — new evidence has landed
     since the edge's newest cited task.
   - **Under-reviewed edges** (curation freshness) — no recent
     `last_reviewed` attestation (opt-in; only if project uses the
     field).
   - **Unresolved refs** — broken IDs in `data_support` / `lit_support`
     / `eliminated_by`.
   - **Unpropagated tasks** — recent DAG-related tasks not cited by
     any edge.
3. For each drifted edge, the skill checks if the candidate drift
   task(s) cite the source/target/hypothesis in a way that supports a
   concrete YAML update. If yes: propose the edit. If unclear: propose
   a review task. The skill does NOT call `science-tool dag audit
   --fix` without explicit user confirmation.
4. On user approval, invoke `science-tool dag audit --fix` (or the
   individual mutation commands — `tasks add`, YAML edits) and
   commit with `doc: refresh DAGs (<slug> + <slug> + ...)`.

**Read-only by default.** The skill's baseline run produces a report,
not mutations. The user approves mutations explicitly.

Referenced from `/science:big-picture` so the synthesis rollup
automatically checks DAG freshness (in read-only mode only).

## Graph vs YAML SoT

The edges.yaml files are a **working materialization layer**, not a
competing source of truth. The long-term picture:

```
doc/inquiries/<slug>.md         # narrative description (authoritative)
         ↓  (manual)
doc/figures/dags/<slug>.dot     # topology                      ─┐
doc/figures/dags/<slug>.edges.yaml  # evidence annotations      ─┤  project-local
         ↓  (science-tool dag render)                            ├  render layer
doc/figures/dags/<slug>-auto.png                                ─┘
         ↕  (science-tool graph sync-dag — future)
knowledge/graph.trig            # canonical triples (phase4b)     upstream SoT
```

Phase 1+3 of this spec stays at the "render layer" side. A future
`science-tool graph sync-dag` bridges the two (reading edge_status
/ identification / posterior / eliminated_by from the triples and
emitting edges.yaml, or vice versa). That bridging is the natural
consumer of the Phase 2 JSON-schema.

The synthesis reports' `structural_fragility(low_connectivity)`
finding is evidence that *today* the YAML layer is richer than the
graph, so the bridge must start with YAML → graph, not the reverse.

## Migration — mm30 consuming the upstream

### Code changes in mm30

**Delete:**
- `doc/figures/dags/_render_styled.py`
- `doc/figures/dags/_number_edges.py`
- `doc/figures/dags/_dag_staleness.py`

**Add to `science.yaml`:**

```yaml
dag:
  dag_dir: doc/figures/dags
  tasks_dir: tasks
```

**Update `doc/figures/dags/README.md`:**
- Replace the "Regenerate" section's three `uv run ... python <script>.py`
  commands with `science-tool dag render`.
- Replace the "Staleness audit" section with `science-tool dag staleness`.
- Keep the `.dot` and `.edges.yaml` files unchanged (they are now the
  upstream-consumed data).

### Behavioural invariant

Running `science-tool dag render` on the current mm30 state MUST
produce byte-identical `<slug>-auto.dot` output to the current local
scripts for all 4 DAGs. `<slug>-auto.png` output must render without
error and pass the structural invariants defined in §"Acceptance
Criteria" (edge/node count, label presence, color-class preservation)
but is NOT required to be byte-identical across graphviz versions.

### Rollout

1. Land Phase 1 (CLI subcommands) in `science-tool` with the mm30
   DAGs as the fixture in `science-tool/tests/dag/fixtures/`.
2. Run the acceptance test: `.dot` byte-identity + `.png` structural
   invariants + ref-schema fail-fast checks.
3. Open mm30 PR that deletes the three local scripts, adds the `dag:`
   block to `science.yaml`, and backfills explicit `identification:
   none` on edges where the axis was previously absent.
4. Land Phase 3 (skill + cadence) in `science-tool` + `science/skills`.
5. Announce in `science-tool`'s changelog + link from `references/`
   (see next section).

## Documentation

New reference doc at
`/mnt/ssd/Dropbox/science/references/dag-two-axis-evidence-model.md`
explaining:

- Why replication and identification are orthogonal
- When to label an edge `interventional` vs `longitudinal` vs
  `observational`
- How to use `eliminated` (and when to resist the urge to delete
  rather than eliminate)
- How `caveats` and `eliminated_by` compose with posteriors
- Cross-reference to `phase4b-causal-dag-design.md`,
  `edge-status-dashboard-design.md`,
  `inquiry-edge-posterior-annotations-design.md`.

## Out of Scope (Phase 2 follow-ups)

- JSON-schema validation of the edges.yaml file
  (`science-tool dag validate`).
- `science-tool graph sync-dag` — bidirectional bridge between graph
  triples and edges.yaml.
- HTML / pyvis / cytoscape.js interactive rendering
  (`science-tool dag render --html`).
- Mermaid / d2 alternative renderers.
- `science-tool dag init` advanced scaffolding (more than dot + empty
  yaml stubs).

## Out of Scope (Phase 4 follow-ups)

- Arrow-head shape encoding for identification (mm30 t254).
- Persistent footer legend variant (mm30 t254).
- Hover-evidence interactive view (mm30 P3 in the discussion).

## Risks and Counter-Arguments

**"Premature generalization — only one project stress-tested this."**
True. The mitigation is Phase 1 scope: lift *as-is* with a `science.yaml`
config shim, don't abstract the schema until a second project exercises
it. Accept that Phase 2 might reshape the schema once evidence accrues.

**"`.dot` SoT locks users into graphviz."** Yes, for Phase 1. Mermaid /
d2 / pyvis renderers are additive in Phase 2+; the YAML is format-agnostic
and can drive any renderer that reads the schema.

**"Duplication with `graph/causal` triples."** The YAML is a
materialization layer, not a rival SoT. Phase 1 does not touch the
triples; Phase 2's `sync-dag` is where the relationship formalizes.
Projects that don't use documentation DAGs simply don't configure the
`dag:` block.

**"Staleness thresholds (28 days) are arbitrary."** Yes; they are the
default and tunable per invocation / per project. The purpose is to
flip "is this edge out of date?" from episodic recall to a
deterministic signal.

## Acceptance Criteria

1. **`.dot` byte-identity + `.png` structural invariants.**
   `science-tool dag render` on the mm30 fixture set produces
   byte-identical `-auto.dot` output vs the local `_render_styled.py`
   (text is deterministic). The `-auto.png` output is NOT required
   to be byte-identical (PNG bytes depend on graphviz version,
   fontconfig, libpng, platform) but must:
   - Render without error (graphviz exit 0).
   - Pass structural invariants: (a) edge count matches the YAML
     edge count, (b) node count matches the `.dot` node count, (c)
     every edge id `[N]` appears somewhere in the rendered label
     layer (verifiable by grepping the intermediate `.dot`), (d) no
     edge loses its status-driven color class (parsed from the
     auto-emitted `.dot` attributes).
   - Optional: perceptual-diff comparison against a reference PNG
     with a tolerance threshold; only required if the test container
     pins the graphviz version.
2. `science-tool dag staleness --json` on the mm30 repo produces a
   JSON report whose `drifted_edges` + `unpropagated_tasks` sections
   match the expected structure (schema-validated). Exact count
   equivalence is NOT required vs the local `_dag_staleness.py` —
   that script uses the age-based signal A which this spec
   supersedes; the new drift-based signal will surface a different
   (and smaller, more actionable) set.
3. mm30 can delete its three local scripts and the rendered
   `-auto.png` files remain stable under subsequent commits modulo
   platform variation.
4. `/science:dag-audit` runs end-to-end on mm30 in read-only mode and
   produces a structured report; `dag-audit --fix` on user approval
   produces a commit-ready refresh diff.
5. `2026-04-17-edge-status-dashboard-design.md` is amended to include
   `eliminated` as a fifth enum value. Graph-layer predicates for
   `eliminated_by` and `identification` are explicitly deferred to
   Phase 2 `sync-dag` and are NOT part of this acceptance test.
6. Ref-schema validation (§"Reference schema") is enforced by
   `dag render` + `dag number`: running either against a fixture
   with a malformed / zero-tag / multi-tag entry must exit non-zero
   with a clear `SchemaError`.
7. In-v1 fail-fast checks present: missing `id`, duplicate `(source,
   target)` edges, malformed `posterior` block (missing `beta` when
   HDI present), and illegal enum values for `edge_status` /
   `identification` all raise `SchemaError` from `dag render`.

## Open Questions

Resolved in this revision (no longer open):
- ~~`eliminated_by` ref shape~~ — resolved in §"Reference schema"
  (tagged one-kind-per-entry; `science-tool refs check` validates).
- ~~`identification` default value~~ — resolved to `none`, not
  `observational`, to avoid converting missing curation into a
  positive evidentiary claim.
- ~~`dag audit --dry-run` semantics~~ — resolved: `dag audit` is
  read-only by default; mutations behind explicit `--fix`.

Still open:

- Where should `/science:dag-audit` write its before/after snapshots?
  (Proposal: `doc/meta/dag-snapshots/YYYY-MM-DD.json`, parallel to
  `doc/meta/dashboard-snapshots/` in the edge-status-dashboard spec.
  Open: does a "snapshot" meaningfully exist for a YAML-on-disk
  layer, or is `git log doc/figures/dags/` sufficient history?)
- Should `last_reviewed: YYYY-MM-DD` be a per-edge field or a
  separate `last_reviewed.yaml` map keyed by edge id? Per-edge keeps
  the provenance co-located; a separate file avoids YAML churn on
  routine reviews. Lean per-edge for v1.
- Should ref-schema validation fail-fast for literature `doi:` entries
  that don't resolve to a local `doc/papers/` file, or stay
  warn-only? (Lean warn-only in v1; mm30's no-fabrication audit
  pattern treats DOI-only citations as acceptable.)
- When mm30 adopts the upstream version, should its existing 85
  `.edges.yaml` records be backfilled with explicit `identification:
  none` where currently missing, or should the default behavior be
  sufficient? (Lean: backfill explicitly during migration; the
  rendering is identical but the curation is more honest.)

## Implementation Sketch

```
science-tool/src/science_tool/dag/
    __init__.py
    cli.py              # click subcommand group
    render.py           # lift from mm30 _render_styled.py
    number.py           # lift from mm30 _number_edges.py
    staleness.py        # lift from mm30 _dag_staleness.py
    schema.py           # Pydantic models (narrow v1; expand in Phase 2)
    paths.py            # science.yaml → dag_dir / tasks_dir discovery

science-tool/tests/dag/
    fixtures/
        mm30-h1-prognosis.dot
        mm30-h1-prognosis.edges.yaml
        mm30-h1-h2-bridge.dot
        mm30-h1-h2-bridge.edges.yaml
        mm30-tasks-subset.md
    test_render_byte_identical.py       # acceptance test 1
    test_staleness_report.py            # acceptance test 2
    test_eliminated_edge_rendering.py   # eliminated-status visual contract
```

Estimated size: ~500 LOC lifted + ~200 LOC test fixtures + ~100 LOC
new (`paths.py`, click wiring, skill). The mm30 originals are already
well-factored, so most of the lift is moving files and updating paths.

## Summary

This spec lifts mm30's proven render + audit stack into `science-tool`
as a `dag` subcommand group, amends the existing 2026-04-17 edge-status
spec to add `eliminated` as a fifth enum value (with graph-layer storage
deferred to Phase 2 `sync-dag`), adds the `identification` sibling axis
at the YAML layer, and adds a `/science:dag-audit` skill for cadenced
maintenance.

**Non-trivial design choices pinned in this revision:**
- **Staleness is drift-based, not age-based.** An edge is flagged only
  when external evidence newer than its newest cited task exists. A
  6-month-old edge with no new related evidence is NOT stale.
- **`dag audit` is read-only by default.** Mutations require `--fix`.
  The `/science:dag-audit` skill runs read-only unless the user
  approves.
- **`identification` defaults to `none`, not `observational`.** Missing
  curation is absence of evidence, never a positive claim.
- **`.dot` byte-identity + PNG structural invariants** (not raw PNG
  bytes) is the rendering acceptance test — PNG bytes are unstable
  across graphviz versions.
- **Tagged-ref schema** formalizes `data_support` / `lit_support` /
  `eliminated_by` entries; all internal refs validated by
  `science-tool refs check`.
- **`--json` output is v1** for `dag staleness` / `dag audit`, not a
  follow-up.

mm30's consumption delta is three deleted scripts + a four-line
`science.yaml` block + README link updates + (one-time migration)
explicit `identification: none` backfill on edges where it was
previously implicit.
