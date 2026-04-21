# Verdict Tokens and Atomic Claim Decomposition

**Status:** rev 1.1 — incorporates 6 schema gaps surfaced in mm30 t243 dogfood
**Created:** 2026-04-19
**Revised:** 2026-04-21 (v1.1)
**Source:** mm30 `discussion:2026-04-19-verdict-polarity-display` + cross-project backfill (~207 docs across 6 projects on 2026-04-19); v1.1 driven by `discussion:2026-04-19-t243-atomic-decomposition-dogfood`
**Related specs:** `2026-04-17-edge-status-dashboard-design.md`, `2026-04-17-inquiry-edge-posterior-annotations-design.md`, `2026-04-18-project-big-picture-design.md`

## Revision history

- **v1.0 (2026-04-19):** initial design surfaced from mm30 cross-project backfill
- **v1.1 (2026-04-21):** dogfood-driven revisions from `discussion:2026-04-19-t243-atomic-decomposition-dogfood` (6 schema gaps; 5/6 dogfooded mm30 docs validated cleanly, 1/6 surfaced a real `rule_disagrees_with_body` case)
  - **Gap 1:** add `closure_terminal:` subfield to `non-adjudicating` rule
  - **Gap 2:** add `reframing_target:` + `reframing_reason:` subfields to `reframed` rule
  - **Gap 3:** add `weighted-majority` rule for the minority-but-load-bearing pattern; document `rule_disagrees_with_body` as an authoritative warning (body wins, rule label flags the mismatch)
  - **Gap 4:** add `members:` claim subfield for grouping similar atomic sub-claims (relevant to `bimodal` rule with many homogeneous atoms)
  - **Gap 5:** strengthen claim-id registry from "advisory" to **required-but-permissive** (must exist; if it does, IDs must resolve; bootstrap helper command)
  - **Gap 6:** add a non-binding `strength:` calibration table to reduce per-author drift

## Problem

Interpretation documents currently express their headline conclusion in
free-form prose. After 207 historical interpretations were backfilled with
plain-text polarity tokens (`[+]` / `[-]` / `[~]` / `[?]`) on 2026-04-19,
two limitations of the single-token-per-doc compression became visible:

1. **The `[~]` token compresses at least 6 distinguishable epistemic
   patterns** (multi-finding panels, per-context divergence, within-result
   bimodality, non-adjudicating terminals, measurement reframings, cross-frame
   mixes). A reader cannot distinguish "we ran 3 sub-tests, 2 passed and 1
   failed" from "the design cannot discriminate" by looking at the token alone.
2. **No structured rollup is possible.** Cross-document queries (e.g.
   "all edges where IFN replicates in both contexts but E2F replicates in
   only one") can't run against unstructured prose. `science:big-picture`,
   `science:status`, the existing `edge-status-dashboard` spec, and the
   `inquiry-edge-posterior-annotations` spec all want structured verdict
   data they could roll up automatically.

The token convention is a foothold; this spec extends it to a layered
machinery (atomic claims at the bottom, composite verdicts above) that
preserves the fast-scanning headline while making the structure
queryable.

The user is already maintaining this data project-locally in mm30 (where
the 207-doc backfill happened) and ~/d/natural-systems (63 backfilled
docs with similar [~]-decomposition pressure on H03/H04 mixed-finding
docs). Lifting the schema into science-tool unlocks rollups for both
projects + every future Science project that adopts the
`interpretation.md` template.

## Token vocabulary

Adopt the five-value verdict-token enum:

| Token | Meaning |
|---|---|
| `[+]` | Positive — evidence supports the predicted direction / hypothesis arm under test. |
| `[-]` | Negative — evidence refutes or contradicts the predicted direction. |
| `[~]` | Mixed — multi-finding panel, per-context divergence, or within-result bimodal. The result has signal but the signal is structured rather than directional. |
| `[?]` | Inconclusive — protocol failure, data gap, or insufficient power; the design cannot discriminate. |
| `[⌀]` | Non-adjudicating terminal — the design *was* able to discriminate at the test layer but the rollup is deliberately closed without resolving polarity (e.g. `non_adjudicating_under_observational_adjusters` in mm30 t204). Distinct from `[?]` (which is a design failure) and from `[~]` (which has structured directional content). |

**Polarity is with respect to the predicted direction, NOT project valence.**
A `[-]` verdict that closes a long-open question is a positive epistemic
event for the project. The token reflects whether the evidence pulled
the prediction's way, not whether the project benefited.

Default for newly-authored interpretations: the `## Verdict` block is
required and must contain exactly one of these tokens. The
`interpretation.md` template (already updated 2026-04-19) carries the
convention; tooling enforces it.

### Why this enum and not a continuous score

A continuous "directional confidence" score (e.g. signed −log10p × sign,
or P(β > 0)) was rejected during the originating discussion
(mm30 `discussion:2026-04-19-verdict-polarity-display`). The reasons:

- The continuous numbers (NES, padj, β/HDI, OR, ρ, P(β>0)) already exist
  in body text and frontmatter. Adding another continuous scalar
  duplicates without compressing.
- The point of the token is fast scanning. Continuous scoring forces
  the reader to interpret a number, defeating the purpose.
- Multi-axis uncertainty (statistical × effect-size × identification ×
  replication) does not collapse onto a single dimension cleanly. The
  separate uncertainty-vector frontmatter (see "Atomic claim
  decomposition" below) carries the multi-axis information when needed.

Continuous representations live at the per-claim atomic layer (effect
+ uncertainty pair), not at the verdict layer.

## Atomic claim decomposition

### Frontmatter schema

Extend the interpretation frontmatter with an optional `verdict` block:

```yaml
verdict:
  composite: "[~]"           # the headline token
  rule: "and | or | majority | weighted-majority | bimodal | non-adjudicating | reframed"
  # rule-specific optional subfields (see Aggregation Rules below):
  closure_terminal: "non_adjudicating_under_observational_adjusters"   # only when rule == "non-adjudicating"
  reframing_target: "interpretation:t149-original-finding"              # only when rule == "reframed"
  reframing_reason: "raw-TPM correlations were ~50% compositional artifact"  # only when rule == "reframed"
  claims:
    - id: "h2#18-edge-6-IFN-arm"        # stable claim ID; resolves via project registry
      polarity: "[+]"
      strength: "strong"                 # strong | moderate | weak — see calibration table below
      weight: 1.0                        # optional; only used by `weighted-majority` rule (default 1.0)
      evidence_summary: "NES=+2.83 RPMI-8226, +2.54 MM.1S, padj < 1e-15 both"
      contexts:                          # optional: per-stratum evidence
        - context: "RPMI-8226"
          polarity: "[+]"
          strength: "strong"
        - context: "MM.1S"
          polarity: "[+]"
          strength: "strong"
      members:                           # optional: group multiple atomic sub-claims with identical polarity/strength
        - "h2#18-edge-6-IFN-arm-RPMI-8226-IFNa"
        - "h2#18-edge-6-IFN-arm-RPMI-8226-IFNg"
        - "h2#18-edge-6-IFN-arm-MM.1S-IFNa"
        - "h2#18-edge-6-IFN-arm-MM.1S-IFNg"
    - id: "h2#18-edge-6-E2F-arm"
      polarity: "[~]"
      strength: "moderate"
      evidence_summary: "NES=-1.47 RPMI-8226 padj=0.0075; NES=-1.09 MM.1S padj=0.32"
      contexts:
        - context: "RPMI-8226"
          polarity: "[+]"
          strength: "moderate"
        - context: "MM.1S"
          polarity: "[~]"
          strength: "weak"
```

All fields are optional inside the block; the *minimum* contract is
`composite` (matches the `## Verdict` token in the body) and either
`claims` (list of atomic claims) or `rule = "non-adjudicating"` (no
sub-claims required if the verdict is a closure).

### `strength` calibration table (non-binding; v1.1 addition)

Per gap 6 from the t243 dogfood, drift was observed across authors on
what `strong` vs `moderate` vs `weak` actually means. The vocabulary
is inherited from the evidence-fragment schema; this table provides
a non-binding calibration to reduce per-author drift:

| Strength | Statistical signal | Effect-size signal | Replication signal |
|---|---|---|---|
| **strong** | HDI excludes 0 with `P(sign)≥0.99`, OR `padj < 1e-3` with confirmatory framing | `|effect|` ≥ ~1 SD on the relevant scale (e.g. NES ≥ 2.0, β ≥ 0.5) | ≥2 independent contexts agree |
| **moderate** | HDI excludes 0 with `P(sign)∈[0.95, 0.99)`, OR `padj < 0.05` with non-trivial effect | `|effect|` in (0.3, 1.0) SD | 1 context only, or 2 contexts with one weak |
| **weak** | HDI crosses 0, OR mechanically significant but explanation-equivocal, OR `padj > 0.05` with sub-threshold framing | `|effect|` < 0.3 SD | single-context, or single-rep |

The table is advisory; project authors may deviate with a one-line
note in `evidence_summary` if their domain warrants different
thresholds. Tooling treats `strength` as opaque (no calibration
enforcement).

### Aggregation rules (`rule` field)

Defines how `composite` derives from `claims`:

| Rule | Composite is `[+]` iff | Composite is `[-]` iff | Composite is `[~]` iff | Notes |
|---|---|---|---|---|
| `and` | all claims `[+]` | any claim `[-]` | otherwise | Conjunctive — every sub-claim must hold for the verdict to hold. |
| `or` | any claim `[+]` | all claims `[-]` | otherwise | Disjunctive — one sub-claim suffices. |
| `majority` | ≥50% claims `[+]` | ≥50% claims `[-]` | otherwise | Voting — n-of-m thresholds. |
| `weighted-majority` | weighted-`[+]` ≥ 50% of total weight | weighted-`[-]` ≥ 50% of total weight | otherwise | Voting with per-claim `weight:` (default 1.0). Use when one or two atomic claims are load-bearing relative to the rest (v1.1 addition; addresses gap 3). |
| `bimodal` | n/a | n/a | always `[~]` | The result IS the distribution shape; no aggregation. Use `members:` subfield (v1.1) to group homogeneous sub-atoms when a per-atom listing is unwieldy. |
| `non-adjudicating` | n/a | n/a | n/a; composite = `[⌀]` | The rollup is deliberately closed; sub-claims may exist but do not aggregate to a directional answer. **v1.1:** name the closure with the optional `closure_terminal:` subfield (e.g., `non_adjudicating_under_observational_adjusters`); free-form, project-local, captured for documentation/tooling but not enum-validated. |
| `reframed` | n/a | n/a | n/a; composite = `[~]` | Original measurement is wrong; new measurement gives different answer. **v1.1:** identify the reframed prior with `reframing_target:` (interpretation-ref) and `reframing_reason:` (string) subfields; required when `rule == "reframed"` so a `science-tool verdict reframed-trail` query can surface the lineage of revised measurements. |

Tooling MUST validate the body's `## Verdict` token against the
rule-derived composite. When they disagree:

- The body composite is **authoritative** (the human-curated verdict line
  is the canonical state).
- The rule label flags the disagreement via a `rule_disagrees_with_body`
  field on `science-tool verdict parse` output.
- The disagreement is informational, not blocking — projects may
  intentionally use a `majority` rule with a body composite of `[~]` when
  one minority claim is load-bearing, AND the disagreement signals to
  reviewers that the rule choice should be reconsidered (often
  `weighted-majority` is the better fit; sometimes the body verdict is
  genuinely the human-judgement override that the rule cannot capture).

The dogfood example: mm30 t163 has 4 claims (3× `[-]`, 1× `[+]` for the
load-bearing `EZH2 → PHF19` edge that survives proliferation adjustment).
Mechanical `majority` gives `[-]`; the body verdict is `[~]` because the
1 surviving edge is the most consequential finding. Either reformulate
as `weighted-majority` with `weight: 2.0` on the surviving claim, or
keep `majority` with the warning firing as the documentation mechanism.

### Claim-id registry (v1.1: required-but-permissive)

Stable claim IDs are **required for cross-doc rollup**. The t243 dogfood
revealed three different naming styles emerging within just 6 docs
without a registry; without canonical IDs, atomic-claim rollups produce
false negatives because the same claim named differently doesn't
aggregate.

**v1.1 contract (changed from v1.0 "advisory"):**

- **Project-local registry at `<project>/specs/claim-registry.yaml`**
  (name canonical; tooling looks here first).
- Maps claim IDs (e.g. `h2#18-edge-6-IFN-arm`) to: (a) the source
  proposition or hypothesis, (b) the predicted direction, (c) any
  synonyms for legacy IDs, (d) optional notes / definition.
- The registry MUST exist for `science-tool verdict rollup --by-claim`
  and `science-tool verdict conflicts --by-claim` to run. Without it,
  these subcommands fail loudly with a pointer to
  `science-tool verdict registry-init`.
- For projects that haven't bootstrapped a registry, basket-level
  rollup (`science-tool verdict rollup` without `--by-claim`) still
  works — it doesn't depend on canonical claim IDs.

**Bootstrap helper:**

```
science-tool verdict registry-init --scan doc/interpretations/
    Walks all interpretations with `verdict.claims:` blocks, collects
    all distinct claim IDs, and writes a stub registry.yaml with
    "definition: TBD" placeholders. Project owner curates the
    placeholders into real definitions + canonicalizes synonyms.
```

This makes the registry **inferred-then-curated** rather than
hand-built-from-scratch. The dogfood found 3 naming styles in 6 docs;
in larger corpora the bootstrap will surface the drift explicitly so
the project owner can choose canonical names before re-using them.

**Tooling contract:**

- `science-tool verdict parse <file>` warns (not errors) on first
  unresolved claim ID per file. Allows authors to introduce new IDs
  during writing and curate the registry after.
- `science-tool verdict rollup --by-claim` errors if registry is
  missing; succeeds if registry exists and all referenced IDs
  resolve; warns and proceeds with opaque-string fallback if
  individual IDs don't resolve (so a partial registry is still useful).

### Claim-id naming convention

Following the existing `h2#18` pattern from mm30 DAG edges:

- `<hypothesis>#<edge>` — claim about a specific DAG edge
- `<hypothesis>-<sub-claim>` — claim about a hypothesis sub-claim
- `<question>` — claim that resolves a registered question
- `<inquiry>#<step>` — claim about an inquiry-step output

Naming is *advisory* — the registry validates that the chosen ID is
unique and resolves to one source artifact. Project owners pick
conventions that fit their domain.

## Parser (science-tool surface)

New science-tool subcommands:

```
science-tool verdict parse <interpretation-file>
    Parses the `## Verdict` block + frontmatter `verdict:` block.
    Validates the composite token matches the rule-derived composite.
    Output: structured JSON with composite + per-claim rows.

science-tool verdict rollup [--scope hypothesis|question|edge|all]
    Aggregates all interpretation verdicts in the project, optionally
    grouped by hypothesis / question / edge.
    Output: per-group verdict-distribution table (cf. existing
    `edge-status-dashboard` spec).

science-tool verdict conflicts
    Finds questions or hypotheses with verdicts of opposite polarity
    across their cited evidence. Surfaces research-friction.

science-tool verdict coverage
    Per-hypothesis polarity distribution. Flags hypotheses with 100%
    one polarity after N≥5 evidence docs (confirmation-bias check).

science-tool verdict watchlist
    Lists [-] verdicts that are the only refutation in their question's
    evidence basket — vulnerable to flipping with one new study.
```

### Backfill helper

```
science-tool verdict backfill --project <path>
    Same logic as the 2026-04-19 cross-project backfill: reads
    interpretation docs without `## Verdict` blocks, dispatches an LLM
    classifier with the rubric, writes audit TSV, leaves edits as a
    diff for human review.
```

This commodifies the manual process the 2026-04-19 backfill executed
(8 subagent dispatches across 6 projects). Future projects adopting the
convention can run one command instead.

## Integration with existing specs

This spec composes with three existing science specs without
overlapping their scope:

| Spec | Composition |
|---|---|
| `2026-04-17-edge-status-dashboard-design.md` | `edge_status` is a separate per-edge field; verdict tokens are a per-interpretation field. Tooling can join: per-edge rollup of verdicts on interpretations that cite the edge → an evidence-weighted edge_status diagnostic. |
| `2026-04-17-inquiry-edge-posterior-annotations-design.md` | `posterior` block stores Bayesian fit values; verdict tokens summarize the *interpretation* of those values. Per-edge rollup can show "posterior + verdict-distribution-from-citing-interpretations" together. |
| `2026-04-18-project-big-picture-design.md` | `science:big-picture` already produces hypothesis rollups. With verdict tokens, the rollup gains a polarity-distribution column for free. |

## Migration story

**Already complete (2026-04-19):**

- Token convention added to global `interpretation.md` template.
- 207 historical interpretations backfilled across 6 projects (mm30,
  natural-systems-guide, seq-feats, protein-landscape, 3d-attention-bias,
  cbioportal). Per-project audit TSVs preserved.
- Token distribution: ~49% `[+]`, ~16% `[-]`, ~28% `[~]`, ~7% `[?]`.

**Migration steps in this spec's scope:**

1. Add the `verdict:` frontmatter block as an OPTIONAL field (no
   project breaks if it's omitted; existing 207 docs continue to work).
2. Adopt `[⌀]` as a fifth token; revise the global template; backfill
   ~5 mm30 docs that currently use `[~]` for non-adjudicating terminals
   (t204 closure, t202 audit, etc.).
3. Implement `science-tool verdict parse / rollup / conflicts /
   coverage / watchlist`.
4. Wire `science:big-picture` and `science:status` to consume the
   structured verdict data.
5. (Optional) Author project-local claim registries for projects that
   want cross-doc rollups; mm30 + natural-systems as the first two.

**Forward-compatible extensions (out of scope here, future specs):**

- Posterior P(verdict) framework — mapping evidence to a probability
  distribution over the 5 tokens
- Claim-graph belief propagation — propagating per-claim posteriors
  through the proposition / hypothesis DAG
- Calibration backtest — auditing whether confidence-tagged verdicts
  are well-calibrated over time
- Reference priors per claim type — different default-replication-rates
  for different evidence categories

These are exploratory follow-ons. mm30 will host reference-use-case
tasks for several of them (P1 in mm30's backlog).

## Reference use cases

The schema must work cleanly on these patterns drawn from existing
mm30 + natural-systems interpretations:

| Pattern | Reference doc | What atomic decomposition adds |
|---|---|---|
| Multi-finding gene panel | mm30 `t221-literature-gene-lookups` | 7 atomic claims (NAT10, CEP170, MAP2K2, YTHDF2, IDO1, IDO2, TDO2) with per-gene polarities; composite via `majority` rule = `[~]` |
| Per-context divergence | mm30 `t197-gse155135-ezh2i-replication` | 2 contexts (RPMI-8226, MM.1S) × 2 arms (IFN, E2F) = 4 atomics; composite via `and` rule on per-arm bothness = `[~]` |
| Within-result bimodal | mm30 `t234-hopfield-hamming-robustness` | 16 atomic claims (one per attractor); composite via `bimodal` rule = `[~]` |
| Non-adjudicating terminal | mm30 `t204-bulk-composition-beyond-pc-maturity-verdict` | 3 sub-rungs (PC-maturity tumor, healthy reference, non-PC multitype) all `no_additional_absorption`; composite via `non-adjudicating` rule = `[⌀]` |
| Measurement reframed | mm30 `t100-q22-closure` (protein-landscape uses similar pattern) | Original q22 answer "PC1-share predicts F53" reframed to "eff-dim drives F53"; composite via `reframed` rule = `[~]` |
| Multi-edge Bayesian DAG fit | mm30 `t163-prolif-adjusted-tf-edges` | 4 atomic claims (one per TF edge) with per-edge β/HDI posteriors; composite via `majority` rule = `[~]` (3/4 collapse, 1/4 survives) |
| Cross-stratum (natural-systems analogue) | natural-systems `2026-03-30-t092-per-theme-kappa.md` | 11 atomic claims (one per theme tier A/B/C); composite via `majority` rule = `[~]` |

## Implementation contract for the parser

`science-tool verdict parse <file>` returns a JSON object of shape:

```json
{
  "interpretation_id": "interpretation:2026-04-19-t197-gse155135-ezh2i-replication",
  "composite_token": "[~]",
  "composite_clause": "Pre-reg verdict Weakly_replicated; IFN arm replicates strongly in both lines; E2F arm replicates only in RPMI-8226, fails in MM.1S",
  "rule": "and",
  "rule_derived_composite": "[~]",
  "rule_disagrees_with_body": false,
  "claims": [
    {
      "id": "h1#edge6-IFN-arm",
      "polarity": "[+]",
      "strength": "strong",
      "contexts": [
        {"context": "RPMI-8226", "polarity": "[+]", "strength": "strong"},
        {"context": "MM.1S", "polarity": "[+]", "strength": "strong"}
      ]
    },
    {
      "id": "h1#edge6-E2F-arm",
      "polarity": "[~]",
      "strength": "moderate",
      "contexts": [
        {"context": "RPMI-8226", "polarity": "[+]", "strength": "moderate"},
        {"context": "MM.1S", "polarity": "[~]", "strength": "weak"}
      ]
    }
  ],
  "validation_warnings": []
}
```

`rule_disagrees_with_body` is `true` when the rule applied to `claims`
produces a different composite than the `composite_token` extracted
from the body's `## Verdict` line. This catches drift between
hand-written verdict prose and the structured frontmatter.

## Open questions for implementation

- **Claim-id registry storage format.** YAML at
  `specs/claim-registry.yaml`? Generated from the proposition / DAG
  graph? Both? The choice depends on how science-tool already manages
  the proposition graph (out-of-scope here; defer to implementation
  discussion).
- **Backwards compatibility for projects without registries.** Should
  `verdict parse` warn loudly when a claim ID doesn't resolve, or be
  silent? Recommend: warn on first miss per file; don't error.
- **Handling of legacy SKIPPED docs.** The 2026-04-19 mm30 backfill
  surfaced 2 docs with pre-existing `## Verdict` sections (in old
  prose-only style). The second-pass solution prepended polarity tokens
  without removing original prose. Should the parser tolerate this
  (multiple verdict-like lines in the same `## Verdict` section)?
  Recommend: yes, the *first* `**Verdict:** [TOKEN]` line in the
  section is canonical; later prose lines are commentary.
- **Pre-registration verdict mapping.** Pre-reg verdicts use a richer
  vocabulary (`Replicated / Weakly_replicated / Null /
  Inconclusive_protocol_failure / no_additional_absorption / etc.`).
  Should the parser auto-map these to the 5-token enum, or require
  explicit `verdict:` frontmatter? Recommend: auto-map for the
  documented patterns (the 2026-04-19 backfill already used the
  documented mapping table); require explicit frontmatter for novel
  pre-reg verdict vocabulary.

## Out of scope (deferred to follow-on specs)

- Posterior P(verdict) framework — full probabilistic treatment of
  per-claim verdicts. Belongs in a separate "verdict uncertainty
  representation" spec.
- Claim-graph belief propagation — propagating per-claim posteriors
  through the proposition DAG to compute marginal hypothesis-state
  beliefs. Composes with `inquiry-edge-posterior-annotations` but
  scope is much larger.
- Calibration backtest framework — using audit-confidence columns to
  test whether the project's self-confidence is well-calibrated.
  Belongs in a separate "verdict calibration" spec.
- Continuous polarity scoring — explicitly rejected during the
  originating mm30 discussion; not revisited in any future spec
  unless new motivation surfaces.
- UI / dashboard rendering — the science-tool parser produces
  structured JSON; rendering choices (HTML dashboard, SVG DAG
  overlays, terminal tables) are renderer-specific and belong in
  whichever interface skill consumes the data.

## Reference: rejected alternatives

These were considered and rejected during the originating discussion:

- **Color-coded verdict tokens.** Rejected because GitHub markdown,
  email, and terminal renderers don't render color uniformly;
  inaccessible to colorblind readers; not grep-able.
- **Single continuous verdict score** (e.g. signed −log10p × sign).
  Rejected because the per-claim continuous numbers already exist;
  adding another scalar at the verdict layer duplicates without
  compressing.
- **Adopting the pre-reg vocabulary as the master enum** (`Replicated /
  Weakly_replicated / Null / Inconclusive_protocol_failure / etc.`).
  Rejected because the pre-reg vocabulary is replication-specific and
  doesn't fit non-replication analyses (e.g. dispositions, methodology
  audits, multi-finding rank lookups). The 5-token enum is more
  general; pre-reg verdicts auto-map to it.

## Acceptance criteria

**v1.0 (original):**

- [x] `[⌀]` token added to the global template with example. *(done 2026-04-19, science commit 765c3d2)*
- [x] `verdict:` frontmatter schema documented in template. *(done 2026-04-19)*
- [ ] `science-tool verdict parse` validates a sample interpretation
  end-to-end.
- [ ] `science-tool verdict rollup` produces a per-hypothesis verdict
  distribution table on mm30 + natural-systems.
- [ ] `science-tool verdict conflicts` runs cleanly on mm30 (the project
  with the most cross-doc adjudication, hence the most likely to
  surface real conflicts). *(hand-emulated on mm30 2026-04-19 per `discussion:2026-04-19-verdict-conflict-coverage-scan` — surfaced 3 actionable findings + 2 spec feedback items)*
- [ ] `science:big-picture` consumes the rollup output (replaces or
  supplements its current prose-summary path).
- [x] mm30 has 6 reference docs authored under the new schema (decomposed `claims:` block) as dogfooding examples. *(done 2026-04-21 per `mm30/discussion:2026-04-19-t243-atomic-decomposition-dogfood`)*
- [ ] natural-systems-guide has at least one reference doc authored under the new schema.
- [x] mm30 has 3 previously-`[~]` docs retokenized to `[⌀]` per the new vocabulary, with audit-trail comment explaining the change. *(done 2026-04-19, mm30 commit 14a94a2: t174, t202, t204 final)*

**v1.1 additions:**

- [ ] `science-tool verdict parse` correctly emits `rule_disagrees_with_body: true` on the t163 reference doc (the one validation case from the dogfood).
- [ ] `science-tool verdict registry-init --scan doc/interpretations/` bootstraps a stub `specs/claim-registry.yaml` from existing `verdict.claims:` blocks. Validate on mm30 (currently 6 docs with `verdict:` blocks).
- [ ] `science-tool verdict rollup --by-claim` runs cleanly on mm30 once the claim registry is curated; produces per-claim aggregated polarity rows.
- [ ] `science-tool verdict reframed-trail <interpretation-id>` resolves the chain of `reframing_target:` links (validate on mm30 CLR doc → t149).
- [ ] `closure_terminal:` field is parsed (free-form string; no enum) and surfaced in `verdict parse` output.
- [ ] `weighted-majority` rule's mechanical aggregation matches expectation when per-claim `weight:` values vary.
- [ ] `members:` claim subfield resolves to the listed member-claim IDs and aggregates their per-member polarity (when those members are themselves registered claims).
