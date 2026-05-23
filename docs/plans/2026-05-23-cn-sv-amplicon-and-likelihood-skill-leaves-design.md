# CN/SV/Amplicon and Likelihood Skill Leaves — Design

**Status:** Approved design (2026-05-23). Next: implementation plan via writing-plans.

**Goal:** Close the last two open downstream-feedback items (T10) by authoring three
new methodology skill leaves and wiring them into the skill index, the relevant
SKILL hubs, and the `plan-analysis` leaf-selection rubric.

**Scope:** Three new leaf documents plus their wiring (INDEX, two SKILL hubs,
`commands/plan-analysis.md`, companion-skill cross-links). No code changes; this
is documentation/methodology content. `test_command_docs` and the skills linter
must stay green.

**Non-goals:** No new validator logic, no template changes, no changes to the
`plan-analysis` workflow beyond rubric rows + one pressure scenario. No
authoring of unrequested leaves (e.g. fusion-transcript QA, methylation QA
remain in the genomics hub's "anticipated growth").

---

## Motivation

Two feedback items from the `evolution` project (`~/d/cancer/mechanisms/evolution`),
both filed against `command:plan-analysis`, report the same class of gap: the
skill INDEX has no leaf for a methodology a real task needed, so planning fell
back to the parent SKILL.

- **fb-2026-05-03-001** — t002 (per-cell CN distributions from DLP+ scWGS) and
  t007 (bulk-WGS AmpliconArchitect/AmpliconClassifier focal-amplicon calls + CN
  segments) both lack a leaf for CN-call / SV-call / AA-pipeline-output QA.
- **fb-2026-05-03-002** — t002 fits Bafna2022 binomial-segregation+selection vs a
  neutral null vs a Wright-Fisher continuous-trait alternative — likelihood-based
  parametric model comparison via AIC/BIC/LRT plus bootstrap CIs — with no
  statistics leaf closer than `survival-and-hierarchical-models` (wrong domain).

Both tasks trace to the ecDNA-evolution work (hypothesis h003, Bafna2022,
Lee2026 scWGS, AA/AC). t002 needs both new statistics leaves *and* the genomics
leaf; t007 needs the genomics leaf. The genomics SKILL already names
copy-number/SV QA as an anticipated future leaf.

## Architecture: three leaves

| New leaf | Path | Covers |
|---|---|---|
| `data-genomics-copy-number-sv-qa` | `skills/data/genomics/copy-number-sv-qa.md` | CN segments (bulk + per-cell scWGS), SV/breakpoint calls, AA/AC focal-amplicon & ecDNA outputs |
| `statistics-likelihood-model-comparison` | `skills/statistics/likelihood-model-comparison.md` | AIC/BIC/LRT hierarchy, nested vs non-nested, identifiability, rare-event numerical precision, bootstrap CIs, re-expression for AIC-comparability |
| `statistics-population-genetics-likelihood` | `skills/statistics/population-genetics-likelihood.md` | Wright-Fisher / Moran / binomial-segregation likelihood construction, neutral-vs-selection comparison |

**Boundary rule (the reason for two statistics leaves rather than one):** leaf 3
owns *what likelihood to write and what it assumes*; leaf 2 owns *how to compare
any likelihoods*. Leaf 3 loads leaf 2 as a companion for the comparison
machinery. This keeps the AIC/BIC/LRT machinery reusable for non-pop-gen model
comparison (cBioPortal/mm30 are likely future consumers) while the pop-gen
domain content stays in its own leaf.

**Why genomics stays one leaf (not split CN/SV vs amplicon):** AA/AC outputs are
built on CN+SV calls and share ploidy/purity QA; t002 (per-cell CN) and t007
(bulk amplicon) both need the combination. Splitting would force both tasks to
load two leaves and would duplicate the ploidy/CN-segment QA.

Each leaf follows the established leaf skeleton (cf.
`skills/data/genomics/somatic-mutation-qa.md` and
`skills/statistics/survival-and-hierarchical-models.md`): frontmatter
(`name`, `description`) → "Use when" intro → checklist → QA tables → Common
Failure Modes → Analysis Rules / Halt-On Conditions → Output Package / Minimum
Artifacts → Companion Skills.

## Leaf content outlines

### Leaf 1 — `data-genomics-copy-number-sv-qa`

- **Acquisition checklist:** lock genome build / coordinate system; name the unit
  of analysis (per-cell ≠ independent; bulk = purity/ploidy-confounded);
  **record the CN-calling method and ploidy/purity correction**; record per-cell
  **bin size / segmentation parameters**; record SV breakpoint support and
  filters; **pin AA/AC version + reference build** and amplicon-type
  classification thresholds.
- **Minimum QA tables:** CN segments, SV/breakpoints, amplicon calls,
  ploidy/purity audit, per-cell binning audit.
- **Common failure modes (maps to feedback a–e):** AA/AC version + ploidy-correction
  drift; **FFPE fragmentation** → false/low amplicon detection and breakpoint
  artifacts; per-cell **CN-binning choices** changing call discreteness;
  **classifier-confidence** handling (ecDNA vs HSR vs BFB vs linear amplification);
  **AA→AC pipeline non-independence** (AA and AC share calls; not independent
  confirmation). Plus GC/mappability waviness and normal-contamination.
- **Analysis rules / Halt-On:** never treat AA + AC as independent confirmation;
  never compare amplicon calls across FFPE/fresh without fragmentation
  adjustment; record ploidy/purity with every CN segment; keep per-cell binning
  fixed across compared cells. Halt when ploidy/purity is unavailable, AA/AC
  versions are unpinned/mismatched, FFPE and fresh are mixed unadjusted, or
  per-cell bins are incomparable.
- **Companion skills:** parent genomics SKILL; `somatic-mutation-qa`;
  `statistics-power-floor-acknowledgement`; `statistics-sensitivity-arbitration`;
  `statistics-population-genetics-likelihood` (downstream consumer of per-cell CN
  for t002).

### Leaf 2 — `statistics-likelihood-model-comparison`

- **Pre-flight checklist:** define the candidate model set and which is the null;
  nested vs non-nested; confirm all models use identical data/observations and
  comparable likelihood normalization; check parameter identifiability; state the
  estimand of the comparison.
- **AIC vs BIC vs LRT hierarchy:** LRT requires nesting + regularity; AIC/BIC
  require identical data and comparable normalization; which metric is
  verdict-bearing vs reported-alongside.
- **Re-expression for AIC-comparability (feedback item b):** the Jacobian/density
  correction required before comparing non-nested AIC across re-expressed /
  common-time-axis variables.
- **Numerical-precision audit (feedback item c):** log-space evaluation,
  logsumexp, underflow on rare-event likelihood evaluators, optimizer
  convergence tolerance.
- **Bootstrap CIs:** parametric vs nonparametric; model-selection stability (how
  often the selected model wins across resamples).
- **Common failure modes / Halt-On:** comparing AIC across different
  datasets/transforms; LRT on non-nested models; treating small ΔAIC as decisive;
  unconverged optimizer; boundary/identifiability issues.
- **Companion skills:** `statistics-sensitivity-arbitration` (pre-commit which
  metric is verdict-bearing); `statistics-power-floor-acknowledgement`;
  `statistics-population-genetics-likelihood` (domain consumer).

### Leaf 3 — `statistics-population-genetics-likelihood`

- **Likelihood construction:** Wright-Fisher (diffusion/transition), Moran,
  binomial-segregation+selection (Bafna2022-style ecDNA); the neutral null vs
  selection alternative vs Wright-Fisher continuous-trait alternative (exactly
  t002's comparison set); what each assumes (effective population size, number of
  generations, selection coefficient).
- **Independent unit and time axis:** generations vs sampling time; per-cell vs
  per-clone; N_e assumptions.
- **Identifiability/confounding:** drift vs selection confounded at low N_e or few
  generations; segregation variance vs selection.
- **Deferral:** comparison metrics + numerical precision defer to leaf 2 (loaded
  as companion).
- **Halt-On:** N_e or generation count unknown; neutral and selection models not
  identifiable on the available data (this is literally t002's documented
  Lee2026-local limitation — promotion requires independent non-Lee2026
  replication).
- **Companion skills:** `statistics-likelihood-model-comparison` (the machinery);
  `data-genomics-copy-number-sv-qa` (the input CN calls);
  `statistics-power-floor-acknowledgement`; `statistics-sensitivity-arbitration`.

## Wiring changes

- **`skills/INDEX.md`:** add the genomics leaf under "Data Modalities" and the two
  statistics leaves under "Statistics".
- **`skills/data/genomics/SKILL.md`:** add the new leaf to the "Two layers" table
  (becomes three) and drop "copy-number QA, structural-variant QA" from the
  "Anticipated growth" list (fusion-transcript and methylation/EPIC-array QA
  remain).
- **`skills/statistics/SKILL.md`:** register the two new leaves in its existing
  leaf listing (match the current format).
- **`commands/plan-analysis.md` Leaf Selection Rubric:** add two trigger rows —
  (a) "CN segments, scWGS/DLP+ per-cell CN, SV/breakpoints, AmpliconArchitect /
  AmpliconClassifier, ecDNA" → genomics leaf + power-floor + sensitivity; (b)
  "likelihood model fit, AIC/BIC/LRT, Wright-Fisher/Moran/segregation,
  selection-vs-neutral" → the two statistics leaves + sensitivity. Add one
  ecDNA-selection **Validation Pressure Scenario**.
- **Companion-skill cross-links** wired per the boundary rule above.

## Verification

No code to run, so verification is content-fidelity against the real project that
filed the gaps (the standing "verify against the real project" rule):

1. Read the t002/t007 plans and the committed
   `pre-registration-h003-t002-ecdna-selection.md` in
   `~/d/cancer/mechanisms/evolution`, and confirm each leaf's checklist /
   halt-on conditions actually cover the methodology those tasks needed — in
   particular that leaf 3's identifiability halt-on names the same Lee2026-local
   limitation the pre-registration records.
2. `test_command_docs` (validates command/skill doc structure) and the skills
   linter must stay green after the INDEX/SKILL/rubric edits.
3. Spot-check that every companion-skill link resolves to an existing path.

## Feedback closure

On completion, close fb-2026-05-03-001 and fb-2026-05-03-002 with resolution
notes naming the leaf paths. This brings the downstream-feedback triage to 27/27.
