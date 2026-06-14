# Schema Adoption Campaign — Design

**Date:** 2026-06-14
**Status:** Approved (design); plan pending
**Depends on:** Spec 1 (typed Data Resource profile), Spec 2 (schema→checks compiler), Spec 3 (`science datasets infer-schema` scaffold)
**Unblocks:** Spec 4 (`science datasets qa` reachability) — its stated precondition is "real authored schemas exist"

## 1. Goal

Bring the durable-reference datapackages of the registered science projects from
schema-less (or names-only) up to **shape + structural invariants**, using the
Spec 3 `infer-schema` scaffold. This is the first real consumer of Specs 1–3: it
dogfoods the scaffold against real data and produces the authored schemas that are
the precondition for Spec 4.

This is primarily a **data-authoring campaign**, not a code build. It requires exactly
one scoped tooling change up front — a real validation gate (Phase 0, §4.0) — because
the current `datasets validate` cannot validate these nested, sometimes-YAML package
descriptors. Beyond that, no `science_tool` / `science_qa` source changes are planned;
if the campaign surfaces a scaffold or compiler defect, that is a separate bug fixed in
its own cycle — the campaign records it and moves on.

## 2. Separation rule (inherited from Spec 3)

The machine writes observed **shape** (field name + coarse type). Humans author
**meaning** (constraints, keys, qa). The hard line, unchanged: *if a wrong inference
could make a future QA run build-fatal, it is never emitted into the schema by
default — it only appears in the review report.* The campaign honors this by keeping
the shape phase (machine) and the meaning phase (human) strictly separated (§4).

## 3. Scope

**In scope** — the `data/external/*` and `data/raw/*` tiers of registered projects
(third-party reference data brought into a project). Only **tabular** resources
(`.parquet` / `.csv` / `.tsv`). Depth of done = **shape + structural invariants**
(`required`, `enum`, `primaryKey`, `foreignKeys`), no `qa:` extension.

**Out of scope** — `results/*`, `data/processed/*`, `data/derived/*` (experiment
outputs and computed artifacts); non-tabular resources (`.json` sidecars,
`*.qa_verdict.json`); the `qa:` distribution layer; Spec 4's `datasets qa` runner;
any push to git remotes.

### 3.1 Target manifest (audited 2026-06-14)

19 packages across four project groups. Per-package tabular-resource counts and
local-data presence as audited:

| Project | Package | Fmt | Tabular | Status |
|---|---|---|---|---|
| mm30 | `data/external/ccle_proteomics/2020-01` | json | 2 | ready |
| mm30 | `data/external/ctrp_v2/2015` | json | 3 | ready |
| mm30 | `data/external/gdsc_v2/2022-07-24` | json | 3 | ready |
| mm30 | `data/external/oetjen_2018/2018-10` | json | 1 | ready |
| mm30 | `data/external/opentargets/25.03` | json | 3 | ready |
| mm30 | `data/external/walker_2024/2024-05` | json | 6 | 2 resources data-missing |
| cancer-therapeutics | `data/raw/chembl-activities` | yaml | 1 | ready |
| cancer-therapeutics | `data/raw/chembl` | yaml | 1 | ready |
| cancer-therapeutics | `data/raw/dgidb` | yaml | 2 | 1 resource data-missing (cross-dir path) |
| cancer-therapeutics | `data/raw/drugcomb` | yaml | 1 | ready |
| cancer-therapeutics | `data/raw/nci-almanac` | yaml | 0 | no-op (no tabular) |
| cancer-therapeutics | `data/raw/nsc-crosswalk` | yaml | 1 | ready |
| cancer-therapeutics | `data/raw/opentargets` | yaml | 1 | ready |
| cancer-therapeutics | `data/raw/string` | yaml | 0 | no-op (no tabular) |
| cancer-evolution | `data/raw/ampliconrepository-kim2024-pcawg` | json | 9 | ready |
| cancer-evolution | `data/raw/ampliconrepository-kim2024-tcga` | json | 9 | ready |
| cancer-evolution | `data/raw/kim2024-supplement` | json | 0 | no-op (no tabular) |
| cancer-evolution | `data/raw/nct02415621-trial-patient-data` | json | 0 | no-op (no tabular) |
| health-meta | `code/scripts/external/reactome` | yaml | 6 | blocked: all data-missing |

**Effective working set ≈ 14 packages, ~41 tabular resources with local data present.**
The 4 zero-tabular packages are recorded N/A; reactome is recorded blocked-on-hydration;
the 3 individually-missing resources (2 walker, 1 dgidb) are skipped and recorded, not
failed. The campaign does not download or hydrate data — a blocked package stays
blocked and is surfaced, not worked around.

## 4. Execution

### Phase 0 — Validation gate (tooling prerequisite)

The campaign's safety gate must actually validate the campaign's targets. The current
`science datasets validate` does not: it scans only `<path>/raw/datapackage.json` and
`<path>/processed/datapackage.json`, JSON-only, and returns a single *warn* (exit 0)
when pointed at a nested or YAML package dir — which would let the Definition of Done be
falsely satisfied with nothing actually validated. Before any authoring, add a focused
exact-descriptor validation capability with these acceptance criteria:

- Accepts a path pointing **directly at a package descriptor or its directory**,
  resolving `datapackage.json`, `datapackage.yaml`, or `datapackage.yml`.
- Parses the descriptor (JSON **or** YAML) and validates every resource through the
  Spec 1 `ResourceDescriptor` models and `package_consistency_issues` — the same SSOT
  that `infer-schema --write` validates against.
- **Fails (non-zero exit)** on any descriptor or consistency error, and also when an
  explicit descriptor target yields nothing to validate (no silent warn-and-pass for an
  explicit target — fail early, per project rules).
- Additive and backward-compatible: the existing `--path data` raw/processed scan is
  unchanged.

This is implemented TDD-first as the plan's first task and is the gate referenced by
Phases 1 and 2 below.

### Phase 1 — Shape (machine, fully safe)

For every **ready** tabular resource:

1. Run `science datasets infer-schema <pkg> --resource <r>` **read-only**; eyeball the
   diff (all `+ add` for schema-less resources; `= same` where names+types already
   present).
2. Run again with `--write` to apply the names+types patch. The command's own
   whole-package post-validation gates the write (refuses on type conflict, validates
   the mutated descriptor through Spec 1 before replacing the file, writes atomically
   in the descriptor's own format).
3. After all resources in a package are written, run the Phase 0 validator against the
   package descriptor to confirm it still parses and passes Spec 1 + package
   consistency.

Commit per repo at the end of Phase 1 (§6). This phase is mechanical; it can run as a
tight loop with my read-only review of each diff.

### Phase 2 — Structural meaning (guided judgment)

One subagent per **package**. For each tabular resource the subagent:

1. Reads the Spec 3 review report (`--emit-suggestions` to a temp YAML) and samples the
   data directly.
2. Authors invariants in two tiers, each with its **own** evidence rule:
   - **Per-resource invariants — must be report-supported *and* data-verifiable.** The
     Spec 3 report surfaces exactly these:
     - `constraints.required` — report shows no nulls *and* the column is genuinely
       mandatory for the dataset's meaning.
     - `constraints.enum` — cardinality is low *and* the value set is a true closed
       domain (not merely small in-sample).
     - single-column `primaryKey` — the report's `identifier` recommendation *and* the
       column is the dataset's real identifier, not incidentally unique in sample (the
       `Description`-as-PK trap from the ccle_proteomics dogfood is the canonical reject).
   - **Relational invariants — governed by direct cross-resource evidence, not the
     per-resource report** (which structurally cannot surface them):
     - `foreignKeys` — author only where local field values are a verified subset of the
       target resource's key column(s) *and* the relationship is meaningful; otherwise
       leave it unauthored.
     - composite (multi-column) `primaryKey` / `uniqueKeys` — author only where the
       column tuple is verified unique-and-non-null across the data *and* is the
       dataset's real key.
3. Never promotes a sample coincidence to an invariant, and never authors a bound
   (`minimum`/`maximum`), `qa:`, or any **per-resource** invariant the report did not
   surface. Sample-derived ranges are explicitly *not* constraints.
4. Runs the Phase 0 validator against the package descriptor; the package must pass
   before the subagent reports done.

I review each package for **over-authoring** — the single failure mode that matters
here: did the subagent emit a *per-resource* invariant the report did not support, a
*relational* invariant without direct cross-resource evidence, or promote a sample
coincidence to an invariant? You spot-check a sample of packages.

## 5. Why human judgment stays in the loop

The Phase-1 dogfood on `ccle_proteomics/mm-proteomics-long` already produced a wrong
recommendation (`Description` → `primaryKey`: unique in the 10k sample, not a real key).
This is the scaffold working as designed — it over-recommends so a human can filter.
The campaign's value is precisely that filtering; an unfiltered `--write`-everything
pass would bake sample coincidences into build-fatal invariants, which is the outcome
Spec 3 was built to prevent.

## 6. Commit protocol (foreign repos)

The target packages live in **separate git repositories outside the science repo**
(mm30, cancer-therapeutics, cancer-evolution, health-meta). Therefore:

- **No worktree.** Work happens **in-place** in each data repo. The Spec-3-era worktree
  isolation does not apply — there is nothing in the science repo to isolate.
- **Verify branch before every commit.** mm30's working copy is Dropbox-synced and its
  branch/HEAD can switch mid-session; re-check the current branch and `cd` to the repo
  root before committing. (See memory `project_mm30_dropbox_repo_branch_volatility`,
  `feedback_subagent_worktree_cwd`.)
- **Named files only.** `git add` the specific `datapackage.{json,yaml}` files touched;
  never `git add -A` / `.`.
- **No push.** All four repos are Dropbox-only / local-main; do not push to any remote.
- **Commit granularity.** One commit per repo per phase (e.g. `chore(schema): infer
  names+types for data/external resources`, then `feat(schema): author structural
  invariants for <pkg>`), so Phase 1 and Phase 2 stay separable in history.

## 7. Tracking

A campaign manifest (the 19 packages × resources, with Phase-1 and Phase-2 status:
`ready` / `done` / `no-op` / `blocked-data-missing`) lives beside this design in the
science repo's `docs/plans/` — the established convention for this work (Spec 1–3
designs and plans all live there). The manifest is updated as packages complete so the
campaign is resumable and its coverage is auditable. It also names, per package, any
scaffold defect or data-hydration gap surfaced, so nothing is silently dropped.

## 8. Risks and how they are handled

- **Over-authoring in Phase 2** (promoting a sample coincidence to a build-fatal
  invariant). → The separation rule + my per-package over-authoring review + your
  spot-check + `validate` gate.
- **YAML round-trip** (cancer-therapeutics descriptors are YAML). → Phase 1 begins with
  one YAML package as a smoke test: confirm `--write` round-trips the mapping cleanly
  (canonical re-render, value-preserved) before processing the rest.
- **Cross-dir / escaping resource paths** (dgidb's `../../processed/...`). → If
  `infer-schema` cannot resolve a path that escapes the package dir, the resource is
  recorded data-missing/blocked, not forced.
- **Branch volatility** (mm30 Dropbox sync). → Branch re-verification before every
  commit (§6).
- **Scaffold defect discovered mid-campaign.** → Recorded in the manifest and fixed in a
  separate science-repo cycle; the campaign does not patch the tool inline.

## 9. Definition of done

The campaign is complete when every **ready** package in §3.1 has: (a) names+types on
all tabular resources (Phase 1), (b) hand-authored structural invariants where
report-supported and data-verifiable (Phase 2), (c) a passing Phase 0 validator run on
its descriptor, and (d) a committed, un-pushed state in its repo. Blocked and no-op packages
are recorded as such. The result is the corpus of real authored schemas that Spec 4
requires.
