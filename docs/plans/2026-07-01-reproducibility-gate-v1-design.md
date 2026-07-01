# Core Reproducibility Gate v1 — Design

- **Status:** Draft (approved in brainstorm 2026-07-01)
- **Date:** 2026-07-01
- **Scope:** `science` framework only (model + planning gate + docs). No `science-commons` work, no CLI surfacing, no backfill.
- **Depends on:** existing dataset `access:` block, the plan data-access gate, the `science.yaml` project-config surface.

## Purpose — the invariant

> Under a **halting** transparency policy, a dataset declared as a **plan input** — or a
> load-bearing external dataset in a derived input's upstream closure — must not pass the
> data-access gate while its reproducibility class is below the policy bar, and an
> **unclassified** input fails loud. The only escape is an explicit, dated, scoped, auditable
> **plan-level waiver**. A `warn` policy is advisory mode: it surfaces the same findings without
> blocking.

Everything in this design serves that one sentence. The framework already answers "can *this
project* access the data" (`access.verified`). It does **not** answer "can an *independent third
party regenerate the analysis*." Those are different questions, and collapsing them is what let a
non-reproducible dataset pass every automated check.

## Motivating failure

A PAIS analysis line locked N3C as its primary vehicle and cleared six blocking checks before a
human noticed the data cannot leave the enclave — not even the synthetic tier is downloadable.
Every automated surface (`dataset list`, `dataset prioritize`, the plan access gate, even
`commons promote`) read `access.verified: true` (`verification_method: credential-confirmed`) as
fully "ready." The framework had no representation of the distinction that actually mattered:
credentialed-insider access vs. third-party-reproducible access. This design adds exactly that
distinction and makes it bite at *plan* time.

## Non-goals (deferred fast-follows)

These are intentionally out of scope for v1. Each only *reads* the classifier this spec
introduces, so they slot in later without reopening the schema contract.

- `dataset list` / `dataset prioritize` columns showing class + gap_reason.
- A `dataset classify` / update helper CLI.
- `science-commons` promotion behavior gated on class; `commons find --reproducible`.
- Bulk backfill / reclassification of existing datasets.
- Any auto-inference of the block beyond what an author writes explicitly.

Existing datasets remain `class: unknown` and only become blocking when declared as a plan input
under a policy that requires classification.

## Data model — `access.reproducibility` (source of truth)

A nested block on the existing `access:` object, following the established `access.exception`
extension pattern: the JSON mixin stays permissive; **the Pydantic access model and its
schema/frontmatter surfaces** (in `science_model/packages/schema.py` and the entity/frontmatter
surfaces around it) are authoritative and enforce the enums.

```yaml
access:
  level: controlled                    # unchanged — "how gated is the SOURCE"
  verified: true
  verification_method: landing-confirmed
  reproducibility:                     # NEW — "can an independent party REGENERATE the analysis"
    obtainability: approved-project    # ≈ Five Safes: safe people / projects
    execution: trusted-environment     # ≈ Five Safes: safe setting
    extractability: aggregate-reviewed # ≈ Five Safes: safe outputs
    notes: "Only disclosure-controlled aggregate outputs leave the enclave."
```

Three explicit controls, each with an `unknown` member. **No stored `class`** — the class is
always derived, so it cannot drift from the controls.

```yaml
obtainability:                         # who can get in
  - public
  - registration
  - self-service-dua
  - approved-researcher
  - approved-project
  - named-collaboration
  - unavailable
  - unknown

execution:                            # where compute runs
  - local
  - hosted-workspace
  - trusted-environment
  - federated-code-to-data
  - custodian-run
  - unknown

extractability:                       # what can leave
  - full-dataset
  - analysis-dataset
  - synthetic-dataset
  - aggregate-unreviewed
  - aggregate-reviewed
  - none
  - unknown
```

`access.level` is retained unchanged and answers a *different* question ("how gated is the
source"). `access.reproducibility` is complementary, not a replacement.

## Derivation — `reproducibility_class_for(access) → {class, gap_reason}`

A pure function living beside the existing `runtime_state_for()` classifier (in
`science_tool/datasets/semantics.py`). It returns the derived class and the controls that pulled
it down, so humans see the *reason*, not just the verdict. A dataset with **no
`access.reproducibility` block at all** derives to `class: unknown` (existing records depend on
this default).

### The class lattice

Known classes are ordered; `unknown` is **not** on the lattice — it is unassessed, not
low-quality, and is handled separately by `policy.unknown`.

```
third-party-reproducible  >  credentialed-reproducible  >  trust-based-output  >  insider-only
unknown = off-lattice; resolved by policy.unknown, never described as "below bar"
```

### The rules (ordered; first match wins)

`insider-only` is checked **before** the broad TRE `trust-based-output` case, so a
custodian-run / named-collaboration route does not get credited as reproducible merely because it
is a "trusted environment." Define **local-rerunnable extractability** =
`extractability ∈ {full-dataset, analysis-dataset, synthetic-dataset}`.

| # | If… | class |
|---|---|---|
| 1 | any of `obtainability` / `execution` / `extractability` is `unknown` | `unknown` |
| 2 | local-rerunnable extractability **and** `obtainability: public` | `third-party-reproducible` |
| 3 | local-rerunnable extractability **and** `obtainability ∈ {registration, self-service-dua, approved-researcher}` | `credentialed-reproducible` |
| 4 | `obtainability: named-collaboration` **or** `execution: custodian-run` **or** `extractability: none` | `insider-only` |
| 5 | repeatable TRE / code-to-data route (`execution ∈ {trusted-environment, federated-code-to-data}`) **and** aggregate outputs (`extractability ∈ {aggregate-reviewed, aggregate-unreviewed}`) | `trust-based-output` |
| 6 | otherwise (fully assessed but unmatched, e.g. `obtainability: unavailable`) | `insider-only` (conservative fail-safe; flag the combo for a possible missing rule) |

Worked: N3C / OpenSAFELY = `approved-project` + `trusted-environment`/`federated-code-to-data` +
`aggregate-reviewed` → not row 4 → row 5 → **`trust-based-output`**. A public GEO download
(`public` + `local` + `full-dataset`) → row 2 → **`third-party-reproducible`**. A self-serve-DUA
downloadable extract → row 3 → **`credentialed-reproducible`**.

`gap_reason` is the human-readable list of controls that determined a non-top class, e.g.
`"approved-project + trusted-environment + aggregate-reviewed"`.

## Policy — `reproducibility_policy` (project + plan)

An **object** (not a bare `bar`) so future behavior (`waiver_expires_after`, `allowed_classes`)
can be added without breaking the interface.

### Project default (`science.yaml`)

```yaml
reproducibility_policy:
  bar: third-party-reproducible   # minimum acceptable KNOWN class for a declared plan input
  unknown: halt                   # how to treat class:unknown inputs — halt | warn (advisory)
  below_bar: halt                 # how to treat a known class below bar with no waiver — halt | warn
```

### Absent policy = opt-in (v1 rule)

"Absent policy" means **neither the project (`science.yaml`) nor the plan** declares a
`reproducibility_policy`. In that case the reproducibility gate is **not enforced** — zero
ecosystem breakage — but it emits a single visible nudge whenever a plan has declared dataset
inputs:

```
WARN reproducibility-policy-missing: plan has dataset inputs but no reproducibility_policy;
     reproducibility gate not enforced.
```

A **plan-level** `reproducibility_policy` is sufficient to opt in even when `science.yaml` is
silent; the effective policy is the plan's policy merged over the project's (plan fields win).
New transparency-bound projects opt in immediately. A later version may flip project templates or
the default to secure-by-default once datasets have broad classification coverage — but that is
explicitly not v1.

### Plan-level override + waivers

The class is an objective property of the access route; **accepting a below-bar dataset is a
contextual decision that belongs to the plan**, not the dataset. A plan may raise/lower the bar
and record waivers:

```yaml
reproducibility_policy:
  waivers:
    - dataset: dataset:n3c-recover-longcovid-synthetic
      accepted_class: trust-based-output
      decision_date: "2026-07-01"
      rationale: "Portability prototype only; no interpretable estimate."
      mitigation: "Outputs labeled non-estimating; barred until a reproducible vehicle exists."
```

A waiver is scoped to one `dataset` + `accepted_class`, dated, and carries `rationale` +
`mitigation`, so every escape is auditable. **Matching is exact:** a waiver applies only when the
dataset id matches **and** the *currently derived* class equals `accepted_class`. If the derived
class later changes — e.g. the access route worsens from `trust-based-output` to `insider-only`,
or drops to `unknown` — the waiver no longer applies and the gate re-evaluates from scratch.

## Enforcement — the plan data-access gate

Layered onto the *existing* access gate (documented in `commands/plan-pipeline.md` Step 2b;
implemented in `science_tool/plan_gate.py`). It runs **after** the current access PASS/DEFER/HALT
checks, and **only for datasets declared as plan inputs**.

| Case | Gate result |
|---|---|
| neither project nor plan `reproducibility_policy` | emit `reproducibility-policy-missing` WARN; do not enforce |
| `class: unknown` | resolve by `policy.unknown` (default **HALT**) |
| known class ≥ `bar` | PASS (surface class + gap_reason) |
| known class < `bar`, no waiver | resolve by `policy.below_bar` (default **HALT**) |
| known class < `bar`, scoped waiver present | PASS-with-recorded-exception |
| below-bar dataset only *discovered* (candidate/reference), not a declared input | WARN / list annotation, never plan HALT |

The "declared plan input" scoping mirrors the existing gate, which already distinguishes
`BoundaryIn` / data-acquisition inputs from incidental references. **For derived inputs,
reproducibility is enforced over the transitive external-input closure** — the same recursion the
existing access gate already performs over `derivation.inputs` — so a plan cannot launder a
`trust-based-output` or `unknown` external dataset through a derived intermediary. The effective
class of a derived input is the **weakest class among its load-bearing external upstreams**
(lowest on the lattice, or `unknown` if any upstream is unassessed).

## Docs & template (the only surfacing in v1)

- `templates/dataset.md`: add the `reproducibility:` block with inline enum comments so authors
  can fill it by hand.
- `docs/user-guide/entities.md`: a short authoring section — the three controls, the Five Safes
  mapping, the class lattice, and three worked examples (public download / credentialed download /
  N3C-style TRE).

## Testing

- `trust-based-output` from an N3C-shaped block (approved-project + TRE + aggregate-reviewed).
- `third-party-reproducible` from a public downloadable block.
- `credentialed-reproducible` from a self-serve-DUA downloadable block.
- `insider-only` from custodian-run / named-collaboration / `extractability: none`, incl. the
  ordering guarantee that it is chosen *before* trust-based-output.
- `class: unknown` when any decision-relevant control is `unknown`; verify it fails loud under the
  default `policy.unknown: halt`.
- below-bar **with** matching waiver → PASS-with-exception; below-bar **without** waiver → HALT.
- absent policy → `reproducibility-policy-missing` WARN and no enforcement.
- non-input discovery of a below-bar dataset → WARN only, never HALT.
- **absent `access.reproducibility` block → `class: unknown`** (existing datasets depend on this).
- **waiver matching:** passes only when dataset id matches **and** derived class equals
  `accepted_class`; if the class worsens or changes, the waiver no longer applies (gate re-halts).
- **derived-input closure:** a plan consuming a derived dataset whose external upstream is
  `trust-based-output` / `unknown` halts (or warns) exactly as if that upstream were a direct input.
- **plan-only opt-in:** a plan-level `reproducibility_policy` with `science.yaml` silent enforces
  (no `reproducibility-policy-missing` nudge).

## Open questions (resolve during planning)

- Wiring `reproducibility_policy` into the typed `science.yaml` loader
  (`science_tool/project_config.py`), and where plan-frontmatter `reproducibility_policy` is parsed.
- Whether the plan gate's "declared input" set is already available at the point enforcement runs,
  or must be threaded through.
- Enum churn: confirm the three enum lists are complete enough for the current dataset corpus
  (they need only be *sufficient*, since `unknown` + the row-6 fail-safe absorb gaps).

## Appendix — standards grounding

The three controls map to the **Five Safes** model (obtainability ≈ safe people/projects,
execution ≈ safe setting, extractability ≈ safe outputs), which OpenSAFELY, N3C, UK Biobank, and
All of Us all instantiate. No existing metadata standard supplies a "reproduction verdict":
DCAT models distribution/access URLs and `accessRights` but not reproducibility; DataCite `Rights`
is licensing; schema.org `conditionsOfAccess` is free text; GA4GH DUO covers use-permissions not
output extractability; DATS is closest in spirit (researcher-reuse framing) but still not a
verdict. Hence a small, purpose-built block deriving a verdict, rather than adopting an external
ontology.
