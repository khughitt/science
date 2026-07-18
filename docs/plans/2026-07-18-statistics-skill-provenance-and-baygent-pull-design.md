# Statistics-skill provenance + baygent-skills content pull — design

Date: 2026-07-18
Status: design (approved scope; revised after spec review — awaiting re-review)

## Motivation

Two needs converge:

1. **Content refresh.** The upstream `Learning-Bayesian-Statistics/baygent-skills`
   repo (MIT, current HEAD `aa940481`, 2026-07-11, authored by Alexandre Andorra)
   has evolved since we last drew Bayesian/causal material from it. A read of its
   current three skills (`bayesian-workflow`, `causal-inference`,
   `amortized-workflow`) plus a sweep of how Bayesian/causal methods are actually
   used across `multiple-myeloma`, `post-acute-infection`, and `natural-systems`
   shows concrete, high-reuse gaps in our `skills/statistics/` library.

2. **Provenance.** Our skills carry no record of the external sources they draw
   on. We want (a) to attribute upstream authors, and (b) a machine-readable
   "dependency tree" so we can tell when a source has moved past the skill that
   drew on it and a refresh is due.

### What the project sweep established

- **Causal identification / adjustment-set derivation** is hand-rolled in **all
  three** projects and gotten wrong on first attempt (post-acute's *locked*
  adjustment set "over-adjusted a mediator"; MM refits `gain(1q)` ~6 ways;
  natural-systems age/community-size confounding of attention→fidelity).
- **Non-identifiability as a terminal verdict** recurs in all three, each with a
  bespoke encoding (latent-U, E-value sensitivity, fail-closed rank).
- **Bayesian workflow + convergence diagnostics** are reinvented (MM via PyMC;
  natural-systems via hand-coded Gelman–Rubin in `emcee`, twice). Our coverage is
  buried inside the survival leaf.
- **Bayesian model comparison** (LOO/ELPD/stacking) is MM's flagship pre-reg; our
  `likelihood-model-comparison.md` is frequentist-only.
- **Mediation** (MM, 5 contradicting implementations) and **MR/IV** (post-acute's
  six-bridge-assumption program) are deep single-project reinventions — deferred
  here to upstream links, per approved scope.

## Goals / non-goals

**Goals**
- A provenance mechanism that costs consuming agents **zero** additional context
  tokens and passes the existing skills linter.
- A curated, upstream-linked content pull ("Moderate" scope): two new statistics
  leaves plus two targeted extensions.
- An actionable dependency tree: `science skills sources` can list source→leaf
  usage and flag skills whose sources have advanced upstream.
- A `docs/plans/` capture of the outstanding toolkit causal gaps as tracked work.

**Non-goals**
- No verbatim copying of baygent prose or PyMC/ArviZ/CausalPy/DoWhy code. We pull
  the tool-agnostic *discipline and checklists* and link upstream for stack
  specifics.
- No mediation, MR/IV, refutation, or amortized/SBI leaves this round (linked
  upstream instead).
- No fixes to the toolkit gaps this session (capture only).
- Provenance frontmatter is added to **skills** only; commands may adopt it later.

## Attribution / licensing

baygent-skills is MIT (`Copyright (c) 2026 Learning Bayesian Statistics`).

**Our position:** the leaves independently express ideas and practices (which are
not copyrightable) and copy **no** substantial prose or code from upstream, so we
regard the pull as ideas-only. But the leaves do retain the upstream workflow's
*selection, ordering, thresholds, and distinctive examples* — enough residual
expression that we do **not** treat "no substantial portion" as settled. Rather
than rest on that judgment, we ship the upstream MIT notice verbatim up front: it
is cheap and removes the ambiguity entirely.

- **`THIRD_PARTY_NOTICES.md` at the repository root** carries the upstream MIT
  license text verbatim (copyright line + full permission notice). It lives outside
  `skills/`, so the skills linter — which treats any `*.md` under `skills/` as a
  skill — never sees it. This satisfies the MIT notice-retention clause regardless
  of how the "substantial portion" question is resolved.
- `sources.yaml` additionally records the upstream authorship and license, plus —
  for git-backed sources — an `attribution_notice` credit line (a short in-registry
  credit, complementary to the root notice; the verbatim license lives in
  `THIRD_PARTY_NOTICES.md`).
- Each drawing leaf ends with a "Deeper dive" line crediting Andorra and linking
  the upstream skill.
- Radev co-authored only the `amortized-workflow` skill, which we do **not** pull;
  `sources.yaml.authors` therefore lists Andorra, with Radev noted in `notes`.

---

## Track 1 — Provenance system

### 1.1 `skills/sources.yaml`

One file at the skills root, a mapping keyed by short source ID. Not an `*.md`
file, so it is exempt from the linter's frontmatter / Companion-Skills /
index-coverage requirements.

```yaml
baygent-skills:
  title: "Baygent Skills — Learning Bayesian Statistics"
  authors: ["Alexandre Andorra"]
  url: "https://github.com/Learning-Bayesian-Statistics/baygent-skills"
  kind: skill-repo            # skill-repo | package-docs | book | paper | course
  license: MIT
  attribution_notice: "Copyright (c) 2026 Learning Bayesian Statistics — MIT; used on an ideas/practices-only basis."
  upstream_ref: "aa940481ebb9fbd087b2fc41dba3af386b5bdb31"   # full 40-hex SHA; the reviewed revision
  last_checked: "2026-07-18"     # ISO string (quoted); informational only
  notes: >
    Pulled: gated Bayesian-workflow spine, calibration, power-scaling prior
    sensitivity, LOO/stacking model comparison, DAG-first identification with the
    M-bias/collider caveat. Radev co-authored the (unused) amortized-workflow.
```

**Field semantics**
- `kind` decides checkability. `skill-repo` / `package-docs` are git-backed and
  revision-comparable via `upstream_ref`. `book` / `paper` / `course` are
  reference-only.
- **`upstream_ref` is the reviewed revision** — the full **40-hex** upstream SHA
  at which we last reconciled *every* citing leaf. It is the single freshness
  signal for the source (see §1.4), validated as `^[0-9a-f]{40}$` so it can
  actually equal what `git ls-remote` returns (an abbreviated `aa940481…` never
  would). Present only for git-backed kinds.
- `last_checked` is an informational human date (ISO string), **not** the
  freshness signal. It is the only date reference-only sources carry.
- `url` is **required for every source** — the canonical locator (git-backed:
  the repo; reference-only: a DOI/arXiv/publisher URL). https scheme.
- Optional typed identifiers: `doi`, `arxiv`, `isbn` (validated shapes when
  present).
- `license` is **required for git-backed** kinds (we may reuse) and **optional /
  omitted for reference-only** kinds — citing a paper or book does not imply its
  content carries a reusable-content license.
- `attribution_notice` — optional short credit line (git-backed). It is a credit
  line, not the verbatim license text; the full verbatim MIT permission notice
  lives in `THIRD_PARTY_NOTICES.md` at the repository root (see Attribution /
  licensing), which is shipped up front rather than deferred.
- Dates are written as **quoted ISO strings**. The loader additionally coerces any
  `datetime.date` (from an unquoted scalar) to an ISO string, so JSON output never
  hits a non-serializable `date` (`output.emit` → `json.dumps`).

**Seed set** (each carries a canonical `url`; verify exact metadata at
implementation):
- `baygent-skills` — as above (primary, git-backed, checkable).
- `gelman-bayesian-workflow` — Gelman et al., "Bayesian Workflow" (2020);
  `kind: paper`, `arxiv: 2011.01808`.
- `vehtari-loo` — Vehtari, Gelman, Gabry, "Practical Bayesian model evaluation
  using leave-one-out cross-validation and WAIC" (2017); `kind: paper`,
  `doi: 10.1007/s11222-016-9696-4`.
- `hernan-robins-whatif` — Hernán & Robins, "Causal Inference: What If" (2020);
  `kind: book`.
- `pearl-primer` — Pearl, Glymour, Jewell, "Causal Inference in Statistics: A
  Primer" (2016); `kind: book`, `isbn: 9781119186847`.
- `vanderweele-ding-evalue` — VanderWeele & Ding, "Sensitivity Analysis in
  Observational Research: Introducing the E-Value" (2017); `kind: paper`,
  `doi: 10.7326/M16-2607` — cited by the causal leaf's sensitivity section.
- `rosenbaum-sensitivity` — Rosenbaum, *Observational Studies* (2nd ed., 2002),
  ch. 4 "Sensitivity to Hidden Bias"; `kind: book`,
  `doi: 10.1007/978-1-4757-3692-2_4`. (Chosen over the 2005 encyclopedia article;
  the earlier draft conflated the two.)

### 1.2 Registry data contract (typed loader)

New `skills_lint/sources.py` defines a typed loader and validation, shared by the
linter (§1.3) and the CLI (§1.4). Validation is explicit and fails early — no
silent acceptance of malformed records:

- Every record must provide `title` (str), `authors` (non-empty list[str]),
  `kind` (∈ the enum above), `url` (canonical locator, **`https` scheme**), and
  `last_checked` (ISO-parseable → normalized to ISO string).
- Optional typed identifiers: `doi`, `arxiv`, `isbn` — **shape-validated by regex**
  when present (`doi` `^10\.\d{4,9}/\S+$`; `arxiv` new/old id forms; `isbn` 10/13
  digits after stripping separators), not merely "non-empty string". Optional
  string fields `license`, `attribution_notice`, `notes` are type-checked (must be
  strings when present). `url` must have an `https` scheme **and a non-empty
  hostname** (`https:foo` is rejected).
- **Conditional by kind:**
  - git-backed (`skill-repo`, `package-docs`): `upstream_ref` required and
    validated as a full 40-hex SHA; `license` required; and the `url` **host must
    be in the fetch allowlist (`github.com`)** — enforced here in the loader so a
    non-GitHub git-backed source is `invalid` in *both* offline and
    `--fetch-upstream` modes, not only when fetched.
  - reference-only (`book`, `paper`, `course`): no `upstream_ref`; `license`
    optional (a citation does not imply a reusable-content license); `url` may be
    any https host (it is never fetched).
- Unknown top-level keys in a record → validation issue (catch typos). The known
  set is: `title, authors, url, kind, license, attribution_notice, upstream_ref,
  last_checked, doi, arxiv, isbn, notes`.
- Loader returns records with all dates as ISO strings (JSON-safe).

### 1.3 Lint extensions

Add to `skills_lint/lint.py`:
- New `IssueKind` members `"unknown-source-ref"` and `"invalid-source-record"`.
- Load + validate `sources.yaml` (via §1.2) from the lint `root`; a missing file
  is treated as an empty registry (skills without `sources:` remain valid).
  Malformed records → `invalid-source-record`.
- For each leaf with a `sources:` value: it must be a list of strings (else
  `invalid-field`), and every ID must resolve to a **declared** source ID (else
  `unknown-source-ref`, offending ID in `detail`). "Declared" = present as a
  top-level key in `sources.yaml`, **whether or not the record is valid** — a
  declared-but-invalid source is reported once as `invalid-source-record` and
  **never also** as `unknown-source-ref`, so the validity and reference axes stay
  orthogonal. The loader therefore exposes `declared_ids` (all keys) alongside
  `records` (valid) and `errors` (a per-ID list of problems, aggregated so one bad
  record yields one report, not one per problem).
- Orphan registry entries (no leaf cites them) are **not** errors — a source may
  be added ahead of the leaf that will cite it.
- Wire into `check_skills` alongside the existing per-file checks.

### 1.4 `science skills sources` subcommand

New `sources` sub-group under the existing `skills_group` (`skills_lint/cli.py`),
sibling of `skills lint`. Both commands reuse `output.emit` for text/json and are
covered by JSON-contract tests (list **and** check) to guard the serialization
boundary.

- `science skills sources list [--root skills] [--format text|json]`
  Builds and prints the dependency tree: for each source ID, the citing leaves
  (and, inverted, per-leaf sources). No network.

- `science skills sources check [--root skills] [--format text|json]
  [--fetch-upstream]`
  - **Default (offline):** validate the registry (§1.2) and every leaf `sources:`
    ID; report each source's `last_checked`. Exit non-zero on any unresolved ref
    or invalid record.
  - **`--fetch-upstream`:** for each git-backed source, resolve the current
    upstream head with `git ls-remote <url> HEAD` and compare the returned **SHA**
    directly to `upstream_ref`. `remote_sha != upstream_ref` ⇒ the source is
    **stale**, and *every* leaf citing it is reported as needing review. No commit
    dates, no filesystem mtimes are consulted — SHA equality is the whole test.
    (Clearing staleness is a human step: review what changed upstream between
    `upstream_ref` and HEAD, update each citing leaf as needed, then bump
    `upstream_ref` to the new SHA. Bump only after all citing leaves are
    reconciled — the source-level ref means the freshness signal is shared across
    a source's leaves by design.)

  **Result contract — three orthogonal axes.** Validity and freshness are
  independent (offline mode cannot establish freshness, and reference-only sources
  have no upstream revision at all), so a single per-source enum is wrong. `check`
  always scans *every* source and leaf before returning (one bad source never
  aborts the scan) and reports each on its own axis:
  - **`validation: valid | invalid`** — record shape/contract (§1.2). Always
    evaluated, in both modes.
  - **`freshness: fresh | stale | unreachable | not_checked | not_applicable |
    unknown`** — `not_applicable` for **valid** reference-only sources (no
    upstream); `not_checked` for **valid** git-backed sources in the default offline
    mode; `fresh`/`stale`/`unreachable` only under `--fetch-upstream`; **`unknown`
    for any invalid record** — an invalid record cannot be classified (a broken
    git-backed record must not falsely claim the reference-only `not_applicable`),
    and file-level registry errors (unparseable YAML, non-mapping document) also
    surface as an `invalid`/`unknown` source so a corrupt registry can never return
    an empty, clean report.
  - **leaf refs: `resolved | unresolved`.** A malformed leaf `sources:` field (not
    a list of strings) is reported as a leaf-level error and fails the check — it is
    never silently dropped from the dependency scan.

  **Exit code:** non-zero if any source is `validation: invalid`, any leaf ref is
  `unresolved`, any leaf has a malformed `sources:` field, or any source is
  `freshness: stale | unreachable`. `not_checked`, `not_applicable`, `unknown`, and
  `fresh` are clean *on the freshness axis* — an invalid record still fails, but via
  the validation axis, not freshness. So the default offline `check` passes a
  well-formed registry, and `unreachable` (indeterminate) is non-zero under
  `--fetch-upstream` because "explicit over silent fallback" forbids reporting an
  undeterminable freshness as clean. The JSON payload carries these axes as explicit
  fields: per source `{id, validation, freshness, last_checked, citing_leaves,
  detail}` (so a stale source names the leaves needing review), every leaf ref as
  `{leaf, ref, status}` with `status ∈ {resolved, unresolved}` (not only the
  unresolved ones), and `leaf_errors` as `{leaf, error}`. `list` emits both
  directions — `by_source` (source → citing leaves) and `by_leaf` (leaf → its source
  IDs). Callers key off the fields, not the exit code alone.

  **Network hardening for `git ls-remote`.** HTTPS scheme alone is **not** SSRF
  protection (an https URL from an untrusted branch can still target an internal
  host). For the current all-GitHub scope the loader **host-allowlists
  `github.com` for git-backed URLs** (§1.2), so a non-GitHub git-backed source is
  `validation: invalid` in *both* modes — validity is never mode-dependent, and
  the fetch only ever sees allowlisted hosts. (If the allowlist grows beyond
  GitHub, additionally reject userinfo, non-standard ports, and private/reserved
  destinations.) The fetch runs with an args list (no shell), a subprocess
  timeout, `GIT_TERMINAL_PROMPT=0` in the environment, and **genuinely bounded
  output** — the reader consumes at most a fixed byte budget (`read(max_bytes+1)`
  on a timeout-guarded thread) and treats an over-budget response as
  `unreachable`, rather than buffering unbounded output and slicing afterwards.
  Unreachable/timed-out/non-zero/oversized/malformed results all become
  `freshness: unreachable` with a `detail`, rather than a hang, a prompt, or a
  crash. The subprocess call sits behind an injectable seam so the args, env,
  timeout, and byte-budget are unit-testable without the network.

**Why source-level, not per-leaf mtime.** An earlier draft stored one global
`upstream_ref` yet claimed `last_checked` tracked per-leaf review — contradictory,
and `git ls-remote` returns a SHA (not a date) while file mtimes neither survive
checkout nor prove a review happened. Source-level SHA freshness removes all of
that: the verdict is exact and reproducible, and different leaves get different
verdicts naturally because they cite different sources. If we later need to bump a
shared source's ref after reviewing only some citing leaves, we can add per-edge
reviewed-revision state; not needed at current scale (YAGNI).

---

## Track 2 — Statistics content (Moderate scope)

### 2.1 New leaf `skills/statistics/bayesian-workflow.md`

- `name: statistics-bayesian-workflow`; description triggers on building/fitting
  probabilistic/Bayesian models, priors, MCMC, convergence diagnostics,
  calibration, and Bayesian model comparison.
- `sources: [baygent-skills, gelman-bayesian-workflow, vehtari-loo]`.
- Body — the gated, tool-agnostic spine:
  1. Formulate model + estimand.
  2. **Prior predictive check** before fitting — simulate from priors, confirm
     implied data ranges are plausible.
  3. Fit (sampler-agnostic: NUTS/nutpie/emcee/NumPyro). Habits: descriptive
     reproducible seed (e.g. `sum(map(ord, name))`, not `42`); save the fitted
     object/InferenceData immediately.
  4. **Convergence gate** — R-hat ≤ 1.01, ESS ≥ 100·chains, divergences = 0,
     tree-depth, E-BFMI. "Do not interpret a failed fit; do not just raise draws
     to hide divergences."
  5. **Model criticism vs calibration** — keep the two distinct:
     - *Posterior predictive checks* assess in-sample fit (data reproduced by the
       fitted model). Necessary but **not** calibration.
     - *Calibration* is out-of-sample: **LOO-PIT** (distinguished from ordinary
       in-sample PIT), **randomized PIT** for discrete outcomes, and **empirical
       coverage** on held-out or simulated datasets; **SBC** when a simulator
       exists. The leaf explicitly warns against presenting posterior-predictive
       fit as calibration.
  6. **Power-scaling prior/likelihood sensitivity** — flag conclusions that hinge
     on the prior (cross-ref `sensitivity-arbitration.md`).
  7. Model comparison → cross-ref the Bayesian arm of
     `likelihood-model-comparison.md`.
  8. Report — interval, not point (HDI/credible interval; no width is magical).
- `## Companion Skills`: `survival-and-hierarchical-models.md`,
  `sensitivity-arbitration.md`, `likelihood-model-comparison.md`.
- "Deeper dive" pointer (crediting Andorra) to upstream baygent `bayesian-workflow`
  for PyMC/ArviZ specifics.
- **De-dup:** shrink `survival-and-hierarchical-models.md`'s "Bayesian
  Diagnostics" section to a pointer here; keep only survival-specific diagnostics
  in that leaf. Add `sources: [baygent-skills]` to it (retro-attribution).

### 2.2 New leaf `skills/statistics/causal-identification.md`

- `name: statistics-causal-identification`; description triggers on causal-effect
  estimation, confounders, adjustment sets, backdoor criterion, DAGs,
  mediator-vs-confounder, collider/M-bias, over-adjustment, "does X cause Y".
- `sources: [baygent-skills, hernan-robins-whatif, pearl-primer,
  vanderweele-ding-evalue, rosenbaum-sensitivity]`.
- Body:
  - **DAG first** — draw it; missing edges are the strongest assumptions.
  - **Estimand before design** — total vs direct effect.
  - **Adjustment-set derivation** — backdoor criterion; exclude descendants of
    treatment; collider/**M-bias** caveat (pre-treatment timing is necessary but
    *not sufficient* to license adjustment — the DAG is the authority).
  - **Over-adjustment** failure mode — cautionary example: the post-acute locked
    set that over-adjusted a mediator, caught only at critique.
  - **When the effect is not point-identified by adjustment** — keep four
    distinct responses separate, because they are not interchangeable:
    1. **Alternative identification strategies**, each conditional on its own
       assumptions — an instrument (IV), the front-door criterion, etc. These can
       *point-identify* an effect if their assumptions hold, **but often a
       different estimand**: an IV under monotonicity identifies a LATE/CACE (the
       complier effect), not the ATE you may have asked for. Require the estimand
       to be **re-stated explicitly** when switching strategy; reject silent
       estimand substitution (answering ATE-shaped questions with a LATE without
       saying so).
    2. **Formal partial identification** — set-identifying bounds (Manski-style)
       that bracket the *target* effect under weaker assumptions.
    3. **Sensitivity analysis** that leaves the effect **non-identified** but
       quantifies robustness to hidden bias — and is scoped to where it applies:
       the **E-value** describes how strong unmeasured confounding would have to be
       to explain away an *association*, on its compatible (ratio-scale)
       effect-measure assumptions — it is not a general identification device;
       **Rosenbaum bounds** apply to matched/stratified observational designs.
       Neither identifies the effect nor supplies causal-effect bounds — do not
       file them under partial identification.
    4. **Fail-closed verdict** — when none of the above licenses a causal claim at
       the current operating point, say so.
  - **Executable path** — three *distinct* entry points, not one:
    `science inquiry validate <slug>` **runs** the identifiability + adjustment-set
    checks in-process and reports the verdict (via
    `CausalInference.get_all_backdoor_adjustment_sets`); `science inquiry
    export-pgmpy <slug>` **emits a pgmpy script** that computes those sets when you
    run it (author the DAG first via `science inquiry` / `sketch-model` /
    `specify-model`); `/science:critique-approach` is an *agentic* adversarial pass
    over the DAG's assumptions and does not compute identifiability. Caveat: the
    in-process checks (`inquiry validate`) require pgmpy or they silently skip
    rather than fail (see Track 3).
- `## Companion Skills`: `survival-and-hierarchical-models.md`,
  `bias-vs-variance-decomposition.md`, `bayesian-workflow.md`.
- "Deeper dive" pointer (crediting Andorra) to upstream baygent `causal-inference`
  for the deferred material (quasi-experimental designs, design-specific
  refutation, the causal-language ladder).

### 2.3 Extend `skills/statistics/likelihood-model-comparison.md`

Add a **Bayesian arm** section: PSIS-LOO / `elpd_loo`, stacking weights, prefer
LOO over WAIC, "comparison is out-of-sample predictive, not variable selection,"
and unreliability signalled by high Pareto-k̂ — using the **library-reported
`good_k` threshold** (`min(1 − 1/log10(S), 0.7)` for `S` draws), not a fixed 0.7.
Update the leaf's frontmatter **description** and its `statistics/SKILL.md` Leaves
row to add LOO/ELPD/stacking triggers, so the Bayesian arm is routable (the
current description is frequentist-only). Add
`sources: [baygent-skills, vehtari-loo]`.

### 2.4 Extend `skills/statistics/sensitivity-arbitration.md`

Add **power-scaling prior/likelihood sensitivity** (PSIS, no refit; flag when the
CJS divergence exceeds ~0.05). Add `baygent-skills` to its `sources:`.

### 2.5 Wiring

- `skills/statistics/SKILL.md` — add the two new leaves to the Leaves table and a
  Principle for each.
- `skills/INDEX.md` — add `statistics-bayesian-workflow` and
  `statistics-causal-identification` entries (lint index-coverage requires it).
- `skills/sources.yaml` — seed set from §1.1.

---

## Track 3 — Toolkit causal gaps (capture only)

New `docs/plans/2026-07-18-causal-tooling-gaps.md` enumerating, with consumer
feedback IDs, no fixes this session:

1. **pgmpy optional → silent skip (fail-open)** — identifiability/adjustment-set
   checks `skip` when pgmpy is absent (post-acute, MM), contradicting the
   project's "a check must be able to fail" doctrine. (Adjacent: fb-2026-05-24-005.)
2. **`inquiry import` status-vocab crash** — pydantic `ValidationError` on MM's
   inquiry statuses (`active`/`descriptive`/`draft` vs the toolkit's
   `sketch|specified|…`); MM fb-2026-07-11-031 / -032.
3. **Unpopulated documented edge schema** — the edge `identification:` /
   `posterior:` schema (`references/dag-two-axis-evidence-model.md`) has no tooling
   to populate or validate it, forcing MM's hand-transcription scripts
   (`_add_identification.py`, `_add_posteriors.py`).

**Not a current toolkit bug (reframed after review):** the earlier-suspected
`export-pgmpy` "empty edge list from a named-graph mismatch" is **already fixed in
the current toolkit** — `causal/export_pgmpy.py:107` reads the per-inquiry named
graph and `:149` unions it with `graph/causal`, and
`tests/test_causal.py::TestExportPgmpy::test_export_pgmpy_reads_compiled_patch_inquiry_edges`
covers it (reran green). The post-acute note reflects an **older pinned toolkit**;
the item is a downstream pin/upgrade, recorded in the doc as such rather than as an
open fix.

Two feature opportunities to note: an "attach a Bayesian fit result to an inquiry
edge" command, and a canonical causal-evidence-ledger schema (three bespoke ones
exist across MM and post-acute).

---

## Testing / validation

- New unit tests under `science/tests/skills_lint/`:
  - Registry validation (`skills_lint/sources.py`): valid record; missing/invalid
    `kind`; missing `url`; non-https url; git-backed record missing `upstream_ref`
    or `license`; **abbreviated `upstream_ref` rejected** (must be 40-hex);
    **non-GitHub git-backed url → invalid in both modes** (loader host allowlist);
    reference-only record with omitted `license` accepted and any-https-host url
    accepted; malformed `doi`/`arxiv`/`isbn`; unquoted-date coercion to ISO
    string; unknown record key.
  - Lint `unknown-source-ref` and `invalid-source-record` rules (resolving and
    non-resolving fixtures; malformed `sources:` list).
  - `science skills sources list` dependency-tree output.
  - `science skills sources check` offline path: git-backed source →
    `freshness: not_checked`; reference-only source → `freshness: not_applicable`;
    **invalid record → `validation: invalid` + `freshness: unknown` and fails**;
    **corrupt/non-mapping registry → an `invalid` source, not an empty clean report**;
    **malformed leaf `sources:` field → a leaf error that fails the check**; validity
    + ref resolution still evaluated. `--fetch-upstream` SHA comparison with
    `git ls-remote` stubbed → `fresh` / `stale` / `unreachable`.
  - **`_run_git` lifecycle tests (all three branches):** the exited path
    (`read(max_bytes+1)`, `GIT_TERMINAL_PROMPT=0`, reaped); the timeout path (a read
    outlasting the deadline → kill **and** wait, returns `None`); and the capped-read
    path with a still-live child (`poll() is None` → kill **before** wait, over-budget
    bytes propagate). A fake reporting `poll()==0` alone would not distinguish the old
    unsafe implementation.
  - **Fetch-mode CLI contract:** through Click with the module `fetch_remote_head_sha`
    monkeypatched — `--fetch-upstream` is forwarded (fetch runs only with the flag),
    and fetch-mode JSON reports `fresh`/`stale`/`unreachable` with `stale`/`unreachable`
    exiting non-zero.
  - **JSON payload contract:** assert the emitted object pins the axes as explicit
    fields — per source `validation` ∈ {valid, invalid} and `freshness` ∈
    {fresh, stale, unreachable, not_checked, not_applicable, unknown}, per leaf ref
    `resolved | unresolved`, plus a `leaf_errors` array — for both `list` and `check`,
    in both modes (not merely that it serializes; dates already ISO strings).
  - **Exit-code contract:** non-zero when any source is `validation: invalid`,
    `freshness: stale`, or `freshness: unreachable`, any ref is `unresolved`, or any
    leaf `sources:` field is malformed; `not_checked` / `not_applicable` / `unknown`
    / `fresh` are clean *on the freshness axis* (offline `check` on a well-formed
    registry exits zero).
  - **JSON-contract tests** for both `list` and `check` (dates serialize as ISO
    strings; no `date`-not-serializable error through `output.emit`).
- Run over the repo: `science skills lint` (new leaves must pass) and
  `science skills sources check`.
- `cd science && uv run --frozen pytest`; `uv run ruff check`; `uv run pyright`.

## File-change summary

New:
- `skills/sources.yaml`
- `THIRD_PARTY_NOTICES.md` (repo root — verbatim upstream MIT notice)
- `skills/statistics/bayesian-workflow.md`
- `skills/statistics/causal-identification.md`
- `docs/plans/2026-07-18-causal-tooling-gaps.md`
- `science/src/science_tool/skills_lint/sources.py` (typed loader + validation)
- tests under `science/tests/skills_lint/`

Modified:
- `skills/statistics/SKILL.md` (Leaves + Principles)
- `skills/INDEX.md` (two entries)
- `skills/statistics/likelihood-model-comparison.md` (Bayesian arm + sources)
- `skills/statistics/sensitivity-arbitration.md` (power-scaling sensitivity + sources)
- `skills/statistics/survival-and-hierarchical-models.md` (de-dup + sources)
- `science/src/science_tool/skills_lint/lint.py` (new rules + registry loading)
- `science/src/science_tool/skills_lint/cli.py` (`sources` sub-group)

## Decisions already made

- Provenance shape: frontmatter IDs + central `sources.yaml` (not self-contained
  frontmatter, not a mapping-only bibliography).
- Freshness: **source-level, direct full-40-hex-SHA comparison**
  (`remote HEAD != upstream_ref`); no commit dates, no leaf mtimes;
  `--fetch-upstream` via `git ls-remote`, **host-allowlisted to `github.com`**.
  `last_checked` is informational, not the signal.
- `check` reports three orthogonal axes — `validation` (both modes), `freshness`
  (`not_applicable` valid-reference-only, `not_checked` valid-offline-git-backed,
  `unknown` for invalid/unclassifiable records, else `fresh|stale|unreachable`), and
  leaf-ref `resolved|unresolved` (plus a `leaf_errors` array for malformed leaf
  `sources:` fields) — pinned as explicit JSON fields. A corrupt/non-mapping
  registry surfaces as an `invalid` source, never an empty clean report. Exit
  non-zero on `invalid` / `stale` / `unreachable` / `unresolved` / any leaf error;
  `fresh` / `not_checked` / `not_applicable` / `unknown` are clean on the freshness
  axis.
- Registry has a typed, kind-conditional loader: `url` required for all;
  `license`/`upstream_ref` and the **`github.com` host allowlist** enforced for
  git-backed (so validity is mode-independent); `license` optional for
  reference-only; typed `doi`/`arxiv`/`isbn`; JSON-safe date handling.
- Content scope: Moderate (two new leaves + two extensions; mediation/MR/
  refutation linked upstream).
- Provenance tooling: data files + `science skills sources` staleness checker.
- Toolkit gaps: `docs/plans/` capture only; the `export-pgmpy` item is reframed as
  a downstream pin/upgrade (already fixed upstream), not an open fix.
- Non-identifiability content separates alternative identification, formal partial
  identification, hidden-bias sensitivity (E-value/Rosenbaum), and fail-closed.
- Attribution: ideas/practices-only position; credit retained via
  `attribution_notice` in the registry; authors = Andorra (Radev noted for the
  unused amortized skill).

## Open questions

- Exact citation metadata for the reference-only seed sources (verify at
  implementation).
