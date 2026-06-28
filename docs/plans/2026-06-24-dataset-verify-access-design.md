---
id: "plan:2026-06-24-dataset-verify-access-design"
type: "plan"
title: "science dataset verify-access — one command for the coupled origin/license/access edit (and legacy backfill)"
status: "proposed"
created: "2026-06-24"
updated: "2026-06-24"
related:
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-06-21-dataset-catalog-cli-design"
  - "plan:2026-06-24-dataset-verify-access-implementation-plan"
---

# `science dataset verify-access` — one command for the coupled origin/license/access edit

## Purpose

Verifying the accessibility of a dataset entity (the `/science:catalog-datasets` Step 3 move) is
*not* a one-field edit. It is a coordinated change across **three coupled fields — `origin`,
`license`, and the `access` block — with order-dependent failure modes** that aren't documented
anywhere the author sees them. There is also **no backfill path** for legacy dataset entities that
carry `source_class` but no `origin`/`tier`/`access`: `science entities migrate` is layout-only
(v2→v3) and has nothing to populate them.

This note proposes a single command, `science dataset verify-access <ref>`, that performs the whole
coordinated edit atomically and idempotently — the author runs one command instead of hand-editing
three interdependent fields in the right order — and that doubles as the legacy backfill.

Tracked as `fb-2026-06-24-018`.

## Background: why this is three coupled fields, not one

The coupling is real and falls straight out of the model. Walking it from the author's point of view:

1. **`access:` alone is inert.** `DatasetEntity.readiness()` dispatches on `origin`; with `origin`
   unset it returns `state="unknown"` (`science/model/src/science_model/entities.py:740`). So adding
   or flipping an `access` block does nothing to readiness — and therefore nothing to the
   `dataset prioritize` weight — until `origin` is also set.

2. **Setting `origin: external` then *requires* an access block** (invariant #7,
   `entities.py:715–717`) — fine, we're adding one — **and trips the `dataset.license-missing`
   warning** unless `license` is non-empty (`science/src/science_tool/validate/checks/dataset_metadata.py:84–92`;
   the check fires only when `license == ""` *and* `origin == "external"`).

3. **Reaching the verified-and-available state** that the author actually wants requires the access
   block to satisfy `_external_readiness` (`entities.py:742–765`): `availability == "available"`,
   no `access.exception.mode`, and `verified == true` → `state="available"` (weight `1.0` in the
   prioritizer, `dataset_prioritize.py:59`). Any one of those wrong yields a lesser/zero-weight state.

So a single conceptual action — "I confirmed I can get this dataset" — touches `origin`, `license`,
and four-plus `access` subfields, in an order where the intermediate states are each individually
broken (inert, or warning-tripping). Today the author must know this sequence; the Step 3 prose
doesn't spell it out.

### Why `dataset add` doesn't already cover it

`science dataset add` scaffolds `origin: external`, `license: "unknown"`, and a full `access` block
for **new** candidates (`science/src/science_tool/datasets_catalog.py:47–67`). The gap is the two
cases `add` doesn't serve:

- **Flip-to-verified** on an existing candidate: set `verified: true` + method + `last_reviewed` +
  the body log line, in one shot.
- **Legacy backfill**: an entity authored before this schema (or by hand) that carries
  `source_class` but lacks `origin`/`tier`/`access` entirely. Nothing backfills these today.

Both are the *same* edit — scaffold-or-update the coupled fields — so one command covers both.

## Proposal: `science dataset verify-access <ref>`

A new subcommand under the existing `dataset` group (`cli.py:5538` neighborhood), backed by a writer
in `datasets_catalog.py`.

### Resolution and guardrails

- Resolve `<ref>` (`slug` or `dataset:slug`) against **local** `entities/datasets/` only — reuse
  `resolve_dataset` / `_resolve_dataset_or_exit` (`cli.py:5593`). Commons datasets are not editable
  in place; refuse with a clear message.
- Refuse `origin: derived` entities up front: invariant #8 forbids an access block on derived
  datasets (`entities.py:722–730`), so "verify access" is meaningless for them. Fail early with a
  message pointing at `dataset register-run`.

### The verified path (Branch A — obtainable under current credentials)

Writes all coupled fields in one atomic, idempotent edit:

- `origin: external` — set if missing; left alone if already `external`.
- `license:` — from `--license <spdx-or-sentinel>`. If the entity already has a non-empty license and
  no `--license` is given, preserve it. If it has none and none is given, **fail early** asking for
  one rather than silently leaving `""` (which would re-trip `dataset.license-missing`). The `unknown`
  sentinel is accepted explicitly when the license genuinely can't be determined. **This rule is
  path-independent**: it applies to *both* the verified and exception paths, because both land
  `origin: external`, and `dataset.license-missing` fires on `origin == "external" AND license == ""`
  regardless of verification state (`validate/checks/dataset_metadata.py:84–92`).
- `access` block:
  - `level:` — `--level` (enum `public|registration|controlled|commercial|mixed`); preserve existing
    or default `public` when scaffolding from nothing.
  - `availability: available`
  - `verified: true`
  - `verification_method:` — **required** `--method {retrieved|credential-confirmed}` (the enum from
    `catalog-datasets` Step 3; it carries epistemic meaning, so no silent default).
  - `last_reviewed:` — today (injected, not `date.today()` inside a pure writer — see Constraints).
  - `verified_by:` — `--by`, default `"agent (verify-access)"`.
  - `source_url:` — `--source-url`; preserve existing if present and not overridden.
- Append a dated line to the body `## Access verification log` (create the section if absent), with
  free-text evidence from `--note`.
- Optionally set `tier:` from `--tier` in the same call (legacy backfill convenience).

### The exception path (Branch B — credentials not held)

Mirror `catalog-datasets` Step 3 Branch B instead of flipping `verified`:

- `--exception {scope-reduced|expanded-to-acquire|substituted}` populates `access.exception.mode`
  plus `decision_date` (today) and, as applicable, `--rationale`, `--superseded-by` (`substituted`),
  `--followup-task` (`scope-reduced`). `decision_date` is a required part of the exception block
  (`AccessException`, `science/model/src/science_model/packages/schema.py:85–93`; lifecycle design
  §access block) — don't omit it.
- **Mutually exclusive with the verified path** (lifecycle invariant: `verified: true` and
  `exception.mode` cannot coexist). The exception path therefore *clears* `verified` to `false` when
  converting an already-verified entity — the command must actively unset it, not just leave it.
- Still writes `origin`/`license` (the path-independent license rule above applies — an exception-gated
  entity that ends `origin: external` with an empty license trips `dataset.license-missing` just the
  same) so readiness resolves to the correct `acquiring` / `consumable-via-*` state
  (`entities.py:753–759`) rather than `unknown`.

### Output and re-validation

- After writing, re-validate in two passes: (a) the existing `_validate_prospective_write`
  (`datasets_catalog.py:116`) for graph/source-audit blockers, and (b) **an explicit metadata pass —
  `evaluate_dataset_metadata([new_fm])` (`validate/checks/dataset_metadata.py:62`) — to surface
  license/tier/cadence warnings.** The first does *not* run the metadata vocabulary checks (it diffs
  source-audit rows), so an unrecognized license would otherwise pass silently. Merge both warning
  lists for display.
- Print the resulting `readiness().state` and its prioritizer weight so the author sees the outcome
  (e.g. `dataset:foo → available (weight 1.0)`), closing the loop that today requires a separate
  `dataset prioritize` run to observe.

### Idempotence / re-review

Re-running on an already-verified entity is allowed: it refreshes `last_reviewed` and appends a new
log line (a real "re-review" workflow — cf. `EpistemicReviewState` horizon, `entities.py:135–143`).
The command never silently downgrades a field the author didn't ask to change.

## Scope decisions

- **One command, not two.** fb-018 floats both a `verify-access` command and a separate
  `dataset migrate` backfill. They are the same edit (scaffold-or-update the coupled fields), so this
  note proposes only `verify-access`, which backfills `origin`/`license`/`tier`/`access` when absent.
  A **bulk** `dataset migrate` that sweeps every legacy entity is explicitly **deferred** — out of
  scope here; revisit only if hand-running `verify-access` per entity proves too slow at scale.
- **`source_class` is left untouched** by default (it's the epistemic class, orthogonal to access).
  Only set it via an explicit `--source-class` if we decide to fold that in; default is hands-off.
- **No new findings/record store.** These are the existing `access` fields and the existing body log
  section — same as `catalog-datasets` Step 3. Do not introduce a parallel record.

## Interaction with fb-017 (reference-class datasets)

For a `source_class: reference` portal (GEO, STRING, …), "verify access" is semantically thinner —
you confirm the *portal* resolves, never that you retrieved a deposit as a unit. `verify-access` will
still work (a portal has an `access.level` and `source_url`), but `verification_method: retrieved`
reads oddly for "I loaded the landing page." This is the same impedance fb-017 raises elsewhere; the
two should be designed together. For now: note the interaction, keep `verify-access` reference-agnostic,
and let the fb-017 design decide whether reference datasets get a distinct verification verb.

## Open questions

1. **Require `--method` always, or infer from `--level`?** Proposal: require it on the verified path
   (epistemic, enum, no safe default). Confirm before implementing.
2. **License default.** Proposal: fail-early when none is known rather than writing `unknown`
   silently; `--license unknown` is the explicit escape hatch. Alternative: default `unknown` with a
   warning. Pick one.
3. **`--tier` here vs. a separate `dataset set-tier`.** Folding `--tier` into `verify-access` is a
   convenience for legacy backfill but blurs the command's verb. Keep it as an optional flag, or
   split it out?

## Validation sketch

Unit tests on the writer (in `datasets_catalog.py`):

- **all-three-fields**: legacy entity with `source_class` only → after `verify-access`, `origin`,
  `license`, and a complete `access` block are all present and mutually consistent.
- **readiness outcome**: the same entity's `readiness().state == "available"` and weight `1.0`.
- **no-warning**: running `validate` (or `evaluate_dataset_metadata`) on the result yields **zero**
  `dataset.license-missing` and `dataset.tier-unrecognized` findings — the order-dependent failure
  modes are gone.
- **idempotent / re-review**: a second run refreshes `last_reviewed` and appends a second log line
  without duplicating or downgrading other fields.
- **Branch B**: `--exception scope-reduced` yields `state="consumable-via-scope-reduced"` (not
  `unknown`, not `available`).

Plus a **CLI-level test** (the unit writer can be correct while the wired command isn't): invoke
`science dataset verify-access <slug> --method retrieved --license ...` on a fixture project and
assert the on-disk entity validates clean and prioritizes at the expected weight. (Same lesson as the
reach design note: unit-green can coexist with a broken out-of-the-box path.)

## Global constraints (implementation)

- Run `uv run --frozen` / `pytest` / `ruff` from `~/d/science/science` with package-relative paths
  (`tests/...`, `src/...`); the repo root has no `pyproject.toml`/`uv.lock`. Git commands run from the
  repo root with `science/...` paths.
- Reuse existing primitives — `resolve_dataset`, `_validate_prospective_write`, `AccessBlock` /
  `_coerce_access`, `validate_slug` — rather than re-deriving frontmatter handling. Compose, don't
  fork.
- Keep the writer pure: inject `today` (as `add_dataset` does, `datasets_catalog.py:90`) rather than
  calling `date.today()` inside it, so tests are deterministic.
- Serialize via `yaml.safe_dump` (as `_render_candidate` does) so user-supplied license/url/note text
  can't break the document.
