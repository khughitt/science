# Feedback Batch T — the execution-geometry cluster

Successor to [Batch S](2026-07-26-feedback-batch-s-design.md). Branch
`feedback-batch-t`, cut from `8db7aad9`.

## The fact

**A measurement taken at a different execution geometry than the one it
authorizes is not evidence about that geometry.**

The mismatch itself has no guaranteed direction. A compile-dominated pilot or
an undersized batch with poor amortization overstates per-unit cost; a batched
benchmark charged to a sequential workload understates it. What makes the error
in *these* filings uniformly optimistic is not the mismatch but **favorable
probe selection** — taking the max over a sweep, benchmarking the convenient
batch size, extrapolating from the fast part of the run. The mismatch destroys
the authorization; the selection supplies the bias.

Stating it as "errs optimistic" would be the same defect the batch is about:
a directional claim inferred from a sample chosen by which incidents got filed.

Batch S's theme was an instrument that cannot see its input reporting a clean
result. This is its cost-side twin: a gate measured somewhere other than where
it applies, reporting affordable over work it never priced.

## Filings

| id | target | measured | authorized | error |
|---|---|---|---|---|
| `fb-2026-07-13-001` | skill:statistics | ODE integrand, batches 1k–32k | sequential pseudo-marginal, `N_inner` ~ tens | 1.7× optimistic; gate flipped PASS→FAIL |
| `fb-2026-07-13-002` | skill:statistics | **max** over a batch sweep | the whole campaign | 1,449 vs 1,000 core-hour envelope; gate FAILED |
| `fb-2026-07-12-014` | skill:pipelines | 60-step pilot, JIT-dominated | 16-process SBC plan | 2.5 h est vs 11.3 h actual; "no slowdown" vs 2.2× |
| `fb-2026-07-25-009` | template:pre-registration | schedule tuned on 244×24 dense | 8,010×367,991 sparse substrate | three ~13 h cycles |
| `fb-2026-07-25-010` | skill:statistics | *nothing* — ladder written unprofiled | remedy ordering | attractive rung addressed 0.2% of runtime |
| `fb-2026-07-25-011` | template:pre-registration | — | — | **positive**: verdict-blind pre-exposure gates made the repeated failures cost nothing |

## Grounding: this is the third wave, not the first

`fb-2026-07-10-012` (evolution/t078, **addressed**) shipped the estimator
doctrine — `skills/study-design/estimator-certification.md`, the four axes, the
ordering rule, and the `Compute budget` row now in
`templates/pre-registration.md`. It fixed **which estimator the budget assumes**.

- Two days later, same project (t079): `07-12-014`, `07-13-001`, `07-13-002`.
  Budget priced on the right estimator, measured at the wrong geometry.
- Twelve days later, a different project (natural-systems/t882): `07-25-009`,
  `07-25-010`. Same again, new substrate.

Three incidents, two independent projects, straddling a fix that addressed the
adjacent axis. This is a **half-applied pattern**, the recurring shape in
`project_toolkit_convergence_umbrella`.

The diagnosis is sharper than "add cost guidance." In the Estimator
Certification Gate table, every axis names its reference domain — Axis 1 *"a
different ERROR-GENERATING MECHANISM"*, Axis 2 *"MAX over R >= 5 replicates —
not the median"*, Axis 3 *"EXECUTED or CONDITIONAL"* with four obligations.
**`Compute budget` is the only row that takes a number and asks nothing about
how it was obtained.** The skill's own failure-mode list names *"the budget
priced on an assumed estimator"* and has no entry for the budget priced at an
assumed geometry.

The doctrine already owns every mechanism these filings request. It applied
them to accuracy and not to cost. `07-13-002`'s line — *"a cost gate that can
only be made to pass by a favourable measurement choice is not a gate"* — is a
restatement of that skill's own listed failure mode, *"a gate that cannot fail,
discharging an obligation it never tested."*

`07-12-014` had already located itself here: *"adjacent to
estimator-certification's 'budget priced on an assumed estimator', but the
mechanism is different — compile amortisation, not estimator choice."*

## The two groups

The filings split by what surface they can bind to. This split drives D3.

**Group A — how to take a measurement** (`07-13-001`, `07-13-002`,
`07-12-014`). Freeze the geometry before measuring; use a near-worst statistic
over repeats at the one geometry that executes, never the best over a sweep;
measure at steady state and at target concurrency. **The defect lives in the
probe script and the reasoning, not in any artifact a validator can read.** A
check here would be fiction.

**Group B — schedule calibration provenance** (`07-25-009`, partly `-010`).
Checkable. `pre-registration:0034` line 154 writes its schedule as *"burn-in =
5 x (number of ones); thinning = 1 x (number of ones) ... the
pre-registration:0026 method"* and imports that calibration onto a 40× larger,
far sparser substrate.

## Rulings

### D1 — doctrine home: a new sibling leaf

`skills/study-design/cost-gate-certification.md`, alongside the existing
focused leaves (`replicate-count-justification.md`, `sensitivity-arbitration.md`,
`power-floor-acknowledgement.md`). `estimator-certification.md` stays at 425
lines and gains one link from its step 3, *"price the design."*

Rejected: a fifth axis inside `estimator-certification.md`. Its argument was
real — the ordering rule *"certify the estimator → price the design → commit
the budget"* lives there and step 3 is the undeveloped one, so a split
separates the rule from its own third step. It loses because cost is not an
estimator-fidelity property: XLA intra-op contention (`07-12-014`) and a
per-draw cost profile showing 99.8% VR/ripser (`07-25-010`) have nothing to do
with how well the estimator computes the model. Composition over inheritance,
and `07-12-014` asks for the separate name outright.

Registration obligations: frontmatter `name: study-design-cost-gate-certification`,
`archetype: analysis-discipline`, `provenance: internal`; a row in
`skills/INDEX.md` (`test_skill_inventory.py::test_registry_rejects_orphan_skill`
fails otherwise); a row in the `study-design/SKILL.md` Leaves table; codex
mirror regenerated.

`07-12-014`'s engineering half stays in this leaf rather than being duplicated
into `skills/pipelines/` — it is the same fact. `skills/pipelines/SKILL.md`
gains a routing pointer so a pipelines-context agent reaches it.

### D2 — template: a Cost Gate section, with its renderer descriptor

`## Cost Gate (execution geometry)` in `templates/pre-registration.md` and its
packaged copy, structured as a table whose every row names its measurement
domain — mirroring the Estimator Certification Gate rather than inventing a
shape.

**A heading alone breaks the renderer.** `_render_body` indexes
`metadata_by_name[parsed.name]` for every parsed section *before* testing
inclusion (`templates.py:277`), so a `##` heading with no `_template.sections`
descriptor raises `KeyError` unconditionally — no flag combination avoids it.
The section therefore ships with:

```yaml
- { key: cost-gate, name: "Cost Gate (execution geometry)", required: false }
```

**`required: false`**, matching the other three conditional gates
(`calibration-gate`, `execution-readiness-gate`, `vehicle-admissibility-gate`).
Requiredness interacts with D3: `required: true` would put the marker in every
newly rendered pre-registration, so a marker-presence check would pass
universally on sight. What makes the gate obligatory is the substantive
antecedent — declaring a sampling schedule — not the renderer default.

**The identical-copy guard already exists.**
`test_templates.py:208` parametrizes over `MIGRATED_KINDS` and byte-compares
root against packaged; `test_packaged_templates_are_exactly_the_migrated_kinds`
keeps that coverage complete. `pre-registration` is migrated. An earlier draft
of this design claimed the guard was missing and proposed adding one — wrong,
and the duplicate is not built. The real hole is D0.

### D0 — the pre-registration template does not render today

Discovered while checking D2's renderer contract, and it **blocks this batch**:
slice 2 edits a template that is already broken.

```
Renderer.render("pre-registration") -> KeyError
  'Training-Side Confound Gate (signature / model-transfer feasibility)'
```

`b8667272` (2026-07-22, Batch J remainder) added that section to the template
body and never added its `sections:` descriptor. **`science` has been unable to
render a new pre-registration for four days.** 1 of 19 migrated kinds is
affected; the other 18 render clean.

Nothing caught it, and the reason is the recorded lesson: **a guard that lists
its scope has a hole by construction.** `MIGRATED_KINDS` is parametrized over
the byte-compare test only. The render tests are hand-picked per kind
(`evidence-line`, one other), so the kind that broke was simply not on the
list. The two copies match perfectly — and both are unrenderable. A guard
comparing the wrong property is this batch's own theme, arrived at from the
toolkit side.

Fix: add the missing descriptor, and parametrize a render smoke test over
`MIGRATED_KINDS` so the scope cannot be listed. Verified red-before/green-after
against the pre-fix template.

### D3 — the check: substitute the one that can fail

**Ship `check:prereg.schedule-calibration-domain`. Do not ship
`check:prereg.cost-geometry-undeclared`.**

The originally chosen check is unfalsifiable against the corpus. Of 46
pre-registrations across the 4 projects that hold any (natural-systems 34,
3d-attention-bias 4, seq-feats 5, protein-landscape 3), **exactly 1 carries the
Estimator Certification Gate and exactly 1 mentions a compute budget.** The
estimator doctrine shipped 15 days ago and the corpus has not adopted it. Such
a check could only be certified against fixtures — and *a fixture that writes
the reader's own convention cannot falsify the reader* is Batch S's lesson
verbatim.

The four gated `prereg.vehicle-*` checks got away with zero corpus findings
because the corpus **had** adopted `vehicles:`; they had material. This has
none.

The substitute has material:

| document | schedule terms | fires today |
|---|---|---|
| `0007` t349 fiber-membership | `Burn-in = 100 * total_edges`, *"independence between samples is best-effort"* | yes |
| `0025` tractability-filter-confound | 4 chains, burn-in, ESS table (1607–3392 of 10,000) | yes — **candidate false positive**, see below |
| `0026` fixed-margin-incidence-null | 19 matches | yes |
| `0032` t878 subset-substructure | 7 matches | yes |
| `0034` arXiv skeleton suppression | 45 matches; the incident | yes |

**Trigger — content, not heading.** An earlier draft suppressed the finding
whenever `## Cost Gate` was present, which would let a blank or placeholder
gate pass. That is a gate that cannot fail, discharging an obligation it never
tested — precisely the defect this batch exists to close, reproduced in the
instrument built to close it.

The rule fires when a **frozen** pre-registration **declares a sampling
schedule** and does not carry a Cost Gate whose two load-bearing rows are
filled:

| row | what it must state |
|---|---|
| **Target geometry** | the geometry that will execute — batch size, call pattern, sequencing, concurrency |
| **Calibration domain** | the substrate and geometry the schedule or benchmark was actually measured on |

"Filled" is checkable: the template writes fill-ins as `<angle-bracket>`
placeholders, so a value cell matching `^<.*>$`, or empty, is unfilled. Two
distinguishable messages under the one rule:

- section absent — *declares a sampling schedule but no Cost Gate*
- section present, row unfilled — *Cost Gate present but `Calibration domain`
  is still a placeholder*

The remaining rows (statistic and repeats, steady-state treatment, transfer
EXECUTED-or-CONDITIONAL) carry the Group A doctrine and are **not** part of the
trigger. They are guidance the leaf teaches; only the two rows above are facts
whose absence is mechanically decidable. Widening the trigger to rows that
require judgement would manufacture findings the check cannot actually
adjudicate.

**Severity WARN, ungated**, following the `vehicle-undeclared` precedent
recorded at `validate/gates.py:82`: an ERROR would be an uncertified instrument
failing real builds for a contract they could not have met.

**Certification domain, stated narrowly:** one project, one method family.
natural-systems does MCMC; the other three projects do none and yield zero
findings. This batch does not get to claim broader coverage than it measured —
its own doctrine applied to itself.

`0025` is the honest risk. It reports achieved ESS per θ on its own substrate,
which is the calibration evidence the check asks for, expressed as a table
rather than a section. If reading it during implementation confirms the finding
is substantively wrong, the antecedent gets refined — learned from the corpus,
not from a fixture.

### D4 — the deferred check is recorded, not silently dropped

`check:prereg.cost-geometry-undeclared` is blocked on corpus uptake (1/46
today), and the results doc says so. A deferral that is written down is a
different thing from a gap.

## Slices

0. **Unbreak the renderer** (D0) — the missing `training-side-confound-gate`
   descriptor, plus a render smoke test parametrized over `MIGRATED_KINDS`.
   Ships first and stands alone: it is a live four-day-old break, independent
   of whether the rest of this batch lands.
1. **Doctrine leaf** — `cost-gate-certification.md` + INDEX row + SKILL.md
   Leaves row + `pipelines/SKILL.md` pointer + codex mirror. Covers Groups A
   and B.
2. **Template gate** — `## Cost Gate` in both copies **with its
   `sections:` descriptor** + the `estimator-certification.md` step-3 link.
   Slice 0's parametrized render test is what proves this one didn't repeat
   `b8667272`.
3. **Check** — `prereg.schedule-calibration-domain` in
   `validate/checks/prereg_vehicles.py`'s neighbourhood, with `_frozen_because`
   extracted to a shared helper (two checks now need it — the Batch S shared-
   resolver pattern), certified by reading all 5 natural-systems findings.
4. **Close the filings** — 5 gaps + 1 positive.

## Exclusions

The other 16 `skill:research` / `skill:statistics` filings remain blocked on the
unmade ruling about where epistemics guidance lives, which pairs with
skills-taxonomy phase 5. This batch takes only the 5 that bind to a concrete
artifact and does not pretend to have unblocked the rest.
