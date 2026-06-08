# Substrate Phase 3c — decision-log promotion + generated `core/decisions.md` view

> Part of the `entities.yaml` retirement line (§B5 of
> `2026-06-06-knowledge-meta-model-and-substrate-design.md`), decomposed into
> **3a (visibility, merged `ce3ea5f7`) → 3b (`--apply` executor, merged `3a0d0335`) → 3c (this doc)**.
> Phase 4 (external-ref resolver + `terms.yaml` retirement) follows.

## Goal

Retire the `decision-log` bucket of `entities.yaml`: promote each real decision
row to an id-preserving owner file under `entities/decision/<local>.md` whose
**body holds the full decision prose**, and make `core/decisions.md` a
**generated view** rendered from those owner files. After 3c, decision identity
and prose are declared in owner files; `core/decisions.md` is render-only.

## Scope decisions (locked during brainstorming)

- **Two deliverables.** (i) content-aware decision-log promotion in the
  retirement executor; (ii) a `core/decisions.md` generator. **AggregateAdapter
  removal is deferred** — it is provably blocked until Phase 4 clears
  `terms.yaml` + the external-ref rows the adapter still loads. The master
  design's "remove `AggregateAdapter` once no aggregate declarations remain"
  cannot fire during 3c; rows remain.
- **Tooling now, live migration later.** Owner files are the long-term prose
  home and `core/decisions.md` is a generated view only (Option 3 with the
  target semantics of Option 1). 3c builds and verifies the parser + generator
  against fixtures and round-trip tests. **The live MM30 prose migration runs
  later, when MM30 is v3-gated** (project Task #30). `--apply` stays v3-gated
  exactly as in 3b, so 3c never mutates v2 MM30.
- **Body is opaque.** MM30's decision log is not simple structured prose (D5
  alone carries amendments, corrections, source addenda, nested rationale). The
  parser extracts only the heading and obvious metadata fields (date, status);
  the section body is preserved verbatim.

## Architecture (Approach A — dedicated module + injected index)

`graph/aggregate_retire.py` remains the orchestration layer. It knows a
`decision-log` row needs specialized promotion but **does not know how to parse
or render decision prose**. All prose knowledge lives in a new
`graph/decision_log.py`. The boundary is an explicit, precomputed
`DecisionLogIndex` injected into the executor — the executor never reaches back
into `core/decisions.md` ad hoc.

```
core/decisions.md ──parse_decision_log──▶ DecisionLogIndex      (migration source only)
  (read once by CLI)                       { "decision:Dn" → DecisionSection }
                                                     │ injected
                                                     ▼
entities.yaml decision-log rows ─▶ plan_retirement(…, promote_decisions, decision_index)
                                                     ▼
                                   apply_retirement(…, decision_index)
                                                     ▼
                                   entities/decision/<local>.md   (owner: frontmatter + opaque body)
                                                     │
entities/decision/*.md ──render_decisions_view──▶ core/decisions.md   (generated view)
```

**Preflight failure mode (the injection payoff):** an `entities.yaml` row says
`decision:D7` but the index has no `D7` section → the planner **rejects** the
row before anything is written.

**Decision rows are governed by `kind`, not by the triage bucket.** The triage
classifier (`aggregate_triage._bucket`) returns `CRUFT` for *any* `migration:*`
source **before** the decision-log rule fires. MM30 has real, prose-backed
decisions (`decision:D9`, `decision:D10`) whose rows carry
`source_path: migration:audit` and would therefore be bucketed `CRUFT` — yet
they have genuine `## D9` / `## D10` headings in `core/decisions.md`. If the
executor keyed off the `decision-log` bucket alone it would miss them, and
`delete_cruft` would **destroy a real decision**. The executor therefore treats
the **injected index as the authority for any `kind == "decision"` row**,
independent of the bucket label (see *Executor hook* below).

## `graph/decision_log.py`

### Data shapes

- **`DecisionSection`** (frozen dataclass):
  - `canonical_id: str` — e.g. `decision:D1`
  - `local_id: str` — e.g. `D1`
  - `title: str` — heading text after the id token
  - `date: str | None`
  - `status: str | None`
  - `body: str` — **opaque verbatim markdown**: everything after the heading
    line, with only the *trailing* view separator stripped. Internal `---`,
    metadata label lines, amendments, and addenda are all preserved.
- **`DecisionLogIndex`**:
  - `sections: dict[str, DecisionSection]` keyed by `canonical_id`
  - `.get(canonical_id) -> DecisionSection | None`

### `parse_decision_log(text: str) -> DecisionLogIndex`

- **Delimiter is the `## ` heading only.** A lone `---` line is *view
  formatting*, never a hard section boundary — otherwise a future decision body
  with an intentional horizontal rule would be truncated. A section runs from
  its `## ` heading to the next `## ` heading or EOF. The leading HTML comment
  and the `# Decisions` H1 are ignored.
- **Heading parser** handles both project conventions:
  - `## D1. Z-score normalization … (2026-03-31)` (MM30, no dash)
  - `## D-001: Scaffold the meta-project …` (science meta)
  - `local_id` = the leading token up to the first `.`, `:`, or whitespace;
    `canonical_id = f"decision:{local_id}"`; `title` = the remainder **with the
    `local_id` token and its trailing `.`/`:` separator stripped** (so the id is
    not duplicated when the view re-emits `## <local_id>. <title>`). For
    `## D1. Z-score … (2026-03-31)`, `title` is
    `Z-score … (2026-03-31)`, **not** `D1. Z-score …`.
- **Metadata extraction** supports **both** label forms and is
  case-insensitive on the label:
  - bulleted: `- **Date:** 2026-03-31`, `- **Status:** active`
  - non-bulleted (MM30's real form): `**Date**: 2026-03-31`, `**Status**: active`
  - extracted `date`/`status` are **queryable copies**; the same lines remain
    verbatim in `body` so the view round-trips.
- **Body capture**: text after the heading line; strip a single trailing
  separator (`---` on its own line, with surrounding blank lines) since the
  generator re-emits it as formatting; everything else verbatim.

### `render_decisions_view(owners: list[DecisionOwner]) -> str`

- `DecisionOwner` is a small read shape over one `entities/decision/<local>.md`
  file: parsed frontmatter (`id`, `title`, `date`, `status`) + the markdown
  body. The generator reads the owner directory into a list of these.
- Reads `entities/decision/*.md` owner files (frontmatter + body).
- **Sort deterministically by natural-numeric `local_id`**: `D1 < D2 < D9 <
  D10 < D18` (the append-only sequential numbering; no reliance on `date`
  presence). Non-numeric suffixes sort after the bare number, lexically.
- Emits a **generated-view header constant defined in `decision_log.py`** — a
  `<!-- GENERATED — do not edit. Source: entities/decision/*.md. Regenerate:
  science entities generate-decisions -->` banner. It deliberately does **not**
  reuse `templates/core-decisions.md`, whose header declares the file
  append-only / "Do not rewrite" / 150-line-capped — semantics that directly
  contradict a render-only artifact. (Updating that template to describe the
  generated view is a live-migration follow-on, not 3c tooling.)
- After the banner: `# Decisions` + for each owner `## <local_id>. <title>`
  (the `title` frontmatter already excludes the id) + the opaque body + a `---`
  separator between sections.
- **Round-trips against `parse_decision_log`**: render → parse yields the same
  `DecisionLogIndex` content (modulo normalized inter-section whitespace).

### Owner file shape (written by the executor, read by the generator)

```markdown
---
id: decision:D1
type: decision
title: "Z-score normalization before metafor effect-size meta-analysis (2026-03-31)"
date: 2026-03-31
status: active
source_path: core/decisions.md
promoted_from: knowledge/sources/local/entities.yaml
---
<opaque body: Decision / Why / Alternatives / Implications / Revisit-if /
amendments / corrections — exactly as captured from the section>
```

`promoted_from` is the 3b crash-recovery marker (write-before-rewrite ordering;
reconcile sweep only deletes stranded aggregate entries whose owner bears *our*
marker — foreign owners are never clobbered).

## Filename strategy: new `verbatim`

MM30's decision local parts (`D1`, `D10`, `D2-treatment-response-category`) are
**uppercase** → the 3b `slug` regex (lowercase-only) rejects all of them.
Decision ids are **sequence identities**, not derived slugs, so they need an
id-preserving strategy.

- Add `"verbatim"` to the `EntityFilenameStrategy` Literal (`entities.py`) but
  **not** to `_VALID_STRATEGIES`. This mirrors `singleton`, which is already
  builtin-only (absent from `_VALID_STRATEGIES`): `_VALID_STRATEGIES` gates
  which strategies a **local manifest** kind may declare, and builtin policies
  are trusted without that check. Keeping `verbatim` out of it reserves the
  strategy for the builtin `decision` kind and prevents arbitrary local kinds
  from minting path-safe-but-unstructured ids. A test asserts a local manifest
  declaring `strategy: verbatim` is rejected.
- `_BUILTIN_MARKDOWN_POLICIES["decision"] = EntityPathPolicy(Path("entities/decision"), "verbatim")`.
- Status vocabulary (required so the migrator/conformance don't `KeyError`, per
  the 3b `concept` precedent):
  - `_DEFAULT_STATUS["decision"] = "active"`
  - `_STATUS_VALUES["decision"] = frozenset({"active", "superseded", "abandoned"})`
  - normalize `superseded by D-XXX` → `superseded`.
- `verbatim` path-safety: `_VERBATIM_RE = ^[A-Za-z0-9][A-Za-z0-9._-]*$` (no
  slashes, no leading dot, no `..`). Branches in `local_part_conforms` and
  `validate_entity_id`.
- **`generate_entity_id` for `verbatim` requires an explicit id** and raises if
  asked to derive one from a title (unlike `slug`, which lowercases the title).
  Sequence identities are never synthesized.
- `entity_layout_migration.py` gains a `verbatim` branch (preserve
  `Path(rel_path).stem`, parallel to the 3b `slug` branch) to guard against
  renumbering during a layout migration.

### Builtin overrides local manifest (stated explicitly)

MM30 currently declares `decision` in its **local** manifest. Once 3c registers
`decision` in `_BUILTIN_MARKDOWN_POLICIES`, the builtin **shadows** the local
kind. This is the intended behavior — `decision` becomes a first-class core
kind with a fixed `entities/decision` root and `verbatim` strategy. A test
asserts `resolve_path_policy("decision", project_root=…)` returns the builtin
policy **even when the local manifest still declares `decision`**.

## Executor hook (`graph/aggregate_retire.py`)

- New `plan_retirement(..., promote_decisions: bool, decision_index: DecisionLogIndex)`
  and `apply_retirement(..., decision_index: DecisionLogIndex)` params.
- **Decision-kind precedence (the High-finding fix).** Because the triage
  classifier sends any `migration:*`-sourced row to `CRUFT` before the
  decision-log rule, the executor must decide **by `kind`, not by bucket**. For
  every row with `kind == "decision"`, when `promote_decisions` is set the
  injected index is the sole authority and takes precedence over the row's
  bucket label:
  - index **hit** → plan a `PROMOTE` to `entities/decision/<local>.md`; owner
    content is built from the `DecisionSection` (frontmatter + opaque body),
    **not** a stub. This is what rescues `decision:D9` / `decision:D10` (bucketed
    `CRUFT` by `migration:audit` source, but real prose-backed decisions).
  - index **miss** → **reject** (reason `"no decision-log section for <cid>"`);
    the row is retained in `entities.yaml`, never written or deleted. Genuinely
    heading-less rows like `decision:D2-treatment-response-category` land here,
    left for human cleanup.
- **`delete_cruft` never deletes a `kind == "decision"` row** — an invariant,
  independent of `promote_decisions`. A decision row classified `CRUFT` (because
  of a `migration:*` source) may still carry real prose in `core/decisions.md`;
  deleting it would lose the record before it can be promoted. Decision rows are
  governed exclusively by the decision path above: promote (index hit) or retain
  (index miss / `promote_decisions` off). When `promote_decisions` is `False`,
  decision rows are simply **untouched** (3b parity — 3b never acted them).
- Reuses 3b primitives unchanged for the promote path: `promoted_from` marker,
  reconcile sweep, one-rewrite-per-file drop-by-index.

## CLI surface (`cli.py`)

- Extend `entities triage-aggregate`: add `--promote-decisions` (composes with
  the existing `--apply` and the v3 `layout_version >= 3` gate). When set, the
  command parses `core/decisions.md` via `parse_decision_log`, builds the
  index, and injects it into `plan_`/`apply_`. No flag → unchanged 3a/3b
  behavior.
- New command **`science entities generate-decisions`**: reads
  `entities/decision/*.md`, calls `render_decisions_view`, writes
  `core/decisions.md`. Dry-run by default (prints), `--write` to apply
  (consistent with the project's generator ergonomics). Also v3-gated.

## Testing

Synthetic fixtures (no live MM30 mutation):

- a `core/decisions.md` fixture with **both** heading styles, **both** metadata
  label forms, and a D5-like section containing an intentional internal `---`
  plus an "Amendment" subsection;
- an `entities.yaml` fixture with decision rows spanning all three cases: a
  `core/decisions.md`-sourced row with a section; a **`migration:audit`-sourced
  row that nonetheless has a real heading** (the D9/D10 case → must promote, not
  be deleted as cruft); and a `migration:audit` row with **no** heading (must be
  rejected/retained).

Tests:

- **parser** — heading variants; dual metadata label forms; opaque-body
  preservation incl. internal `---`; missing `date`/`status`; `title` excludes
  the leading id token.
- **generator** — deterministic natural-id order (`D1 < D2 < D10`); the
  `decision_log.py` generated-view banner (not the append-only template header);
  `## <local_id>. <title>` renders with no duplicated id; section separators.
- **round-trip fidelity (semantic, not byte-equal)** — the headline safety
  test, asserted on **content**, not the whole file. The regenerated file
  deliberately carries the new `decision_log.py` banner instead of the
  original/MM30 header, so whole-file equality is wrong by construction. The
  contract is: `parse(original).sections == parse(rendered).sections`, i.e. the
  same set of `canonical_id`s, and for each section the **`title`, `date`,
  `status`, and opaque `body` are preserved**. Header and inter-section
  formatting (banner, blank lines, `---` separators) are explicitly excluded
  from the comparison (the parser already strips them).
- **filename strategy** — `verbatim` conformance (accepts `D1`,
  `D2-treatment-response-category`; rejects slashes / leading dot / `..`);
  `generate_entity_id` raises without an explicit id; migrator `verbatim`
  branch preserves stem; a **local manifest declaring `strategy: verbatim` is
  rejected** (builtin-only).
- **builtin-overrides-local** — `resolve_path_policy("decision", …)` returns the
  builtin even with a local-manifest `decision`.
- **executor** — decision-kind precedence: a `migration:audit` decision row with
  an index hit is **promoted** (not cruft-deleted); `delete_cruft` together with
  `promote_decisions` never deletes any `kind == "decision"` row; index-miss
  decision row is rejected/retained; apply writes owner content from the section
  (not a stub); crash-recovery marker + reconcile; v3 gate refuses on v2;
  no-flag run leaves decision rows untouched (3b parity).
- **CLI** — `--promote-decisions --apply` on a v3 fixture; `generate-decisions`
  dry-run + `--write`.

Run: `cd ~/d/science/science && uv run --frozen pytest`. Lint:
`uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char).

## Non-goals (deferred)

| Deferred item | Phase |
|---|---|
| Remove the `AggregateAdapter` deprecated-owner mode | Phase 4 close-out (blocked on `terms.yaml` + external-ref) |
| Live MM30 decision prose migration + regenerating MM30's real `core/decisions.md` | project Task #30 (v3 cutover) |
| Clearing AGENTS.md `_Digest pending_` live | follows the MM30 generator run; tooling-only here |
| `terms.yaml` / external-ref / ambiguous bucket retirement | Phase 4 |
| Reconciling heading-less decision rows (e.g. `decision:D2-treatment-response-category`) | human cleanup after they are rejected/retained |

## Acceptance

- `entities/decision/*.md` owner files carry full decision prose; identity is
  declared there, not in `core/decisions.md`.
- `core/decisions.md` is produced solely by `render_decisions_view`; the
  round-trip test proves no prose is lost.
- `decision` is a core `verbatim` kind; builtins override local manifests.
- The executor promotes any index-hit decision row (even one bucketed `CRUFT`
  by a `migration:*` source) and rejects heading-less rows without writing;
  `delete_cruft` never deletes a decision-kind row.
- `--apply` and `generate-decisions` are v3-gated; the suite is green and the
  3b ruff baseline is unchanged.
