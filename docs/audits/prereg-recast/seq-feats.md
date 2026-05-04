# Pre-registration recast audit — seq-feats

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/seq-feats`
**Scope:** all 5 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

seq-feats has 5 pre-regs, all `status: active` and all targeting `hypothesis:h01-raw-feature-embedding-informativeness` (its primary hypothesis). The audit found:

- **All 5 pre-regs have non-canonical frontmatter** (no `id:`, no `type:`, no `committed:`; `status: active` is also non-canonical — the canonical vocabulary is `draft` / `committed` / `complete`). This is a pre-existing data-quality issue independent of the recast.
- **All 5 pre-regs are mixed** (epistemic targets + operational tasks in `related:`). The body language ranges from heavily operational (cycle1-domains: V1/V2/V3 validation tiers + C1/C2/C3/C4 confirmatory tiers + diagnostic ranges) to clean epistemic-arm (t152-bpe-nda: explicit decision criteria with three outcome buckets and a recast-spirit null-result plan).
- **Confirms the cross-project pattern from natural-systems and protein-landscape** — pre-regs use `related:` for both commitment targets and navigation context, and the project's primary hypothesis (H01) appears in every pre-reg's `related:` regardless of whether the pre-reg actually commits to interpreting H01 or is operationally locking a procedure that incidentally tests H01.

**Recommendation for seq-feats:** no file edits required. The recast handles all 5 pre-regs cleanly once the recurrent `related:` conflation issue is resolved in the recast plan. Frontmatter regularization is independent of t012 and worth queuing as a separate cleanup pass.

---

## Inventory and classification

| # | File | Status | Outcome | Epistemic targets | Operational targets | Class | Notes |
|---|---|---|---|---|---|---|---|
| 1 | `pre-registration-cycle1-domains.md` | active (non-canonical) | — | h01, q60, q61, q62, 2 interpretations | t127, t130, t131, t132 | mixed | Heavy V1/V2/V3 + C1/C2/C3/C4 structure; mostly operational |
| 2 | `pre-registration-phase3b-validation.md` | active (non-canonical) | — | h01, q54, q50 | (no entity-form refs in `related:`; `source_refs:` has `task:2026-03-11-phase3b`) | mixed | Phase-gate pre-reg (Phase 3B → Phase 3+) |
| 3 | `pre-registration-t138-cross-feature.md` | active (non-canonical) | — | h01, h04, 3 source-refs (interpretation, discussion) | t138, t124, t134 | mixed | Cross-feature robustness analysis |
| 4 | `pre-registration-t143-contextual-kmer.md` | active (non-canonical) | — | h01, h02, interpretation | t143, t142 | mixed | k-mer context vs sequence identity |
| 5 | `pre-registration-t152-bpe-nda.md` | active (non-canonical) | — | h01, q84 | t147 | mixed | **Cleanest epistemic-arm shape of the 5** |

### Classification breakdown

- **Pure-epistemic:** 0
- **Pure-operational:** 0
- **Mixed:** 5 (all)

H01 appears in every pre-reg's `related:`. This is signal-by-itself: in a project organized around a single primary hypothesis, every pre-reg gets that hypothesis listed for navigation/discoverability — regardless of whether it commits to an interpretation rule for that hypothesis. **This is exactly the `related:` conflation pattern surfaced in natural-systems' audit.**

### Frontmatter anomaly (pre-existing, not a recast issue)

None of the 5 pre-regs match the canonical pre-reg shape from `docs/plans/2026-04-25-pre-registration-canonical-type.md`:
- Missing `id:` (canonical: `pre-registration:<slug>`)
- Missing `type:` (canonical: `"pre-registration"`)
- Missing `committed:` (canonical: date the criteria are locked)
- `status: active` is non-canonical (canonical vocabulary: `draft` / `committed` / `complete`)

The `status: active` value reads as "in-progress and not yet finalized" but the bodies look like they were intended to be committed (specific thresholds, locked methods, "Decision Criteria" sections). The semantic mismatch suggests these pre-regs were authored before the canonical shape was stabilized in the 2026-04-25 design document.

**This is a pre-existing data-quality issue independent of the recast.** Mentioned for awareness; resolution is out of t012 scope.

---

## Author-intent vs. recast interpretation

### `cycle1-domains` — heavily operational with epistemic context

The body opens by framing protein domains as "the highest-novelty test in the Phase 3+ plan" and lays out **V1/V2/V3 validation tiers** (pipeline reproduction, data acquisition quality, T3 control calibration) and **C1/C2/C3/C4 confirmatory tiers** (token-freq baseline, T1/T2 calibration, same-fold T3, cross-fold T3) with explicit AUC ranges per tier.

The expected-outcomes section gives ranges for each tier (e.g., "T3 AUC 0.55-0.70 for the 12 clan-filtered families"). The hypothesis-portion (H01) is in `related:` for context — the actual commitment is to *the experiment design and analysis tiers*, not to "if T3 AUC > X then H01 is supported."

Same shape as natural-systems' h07-beta-arbitration and protein-landscape's t098: operational pre-reg with epistemic entities in `related:` for navigation. → cross-project pattern (Issue 1) confirmed.

The pre-reg also has a **mid-stream amendment** (the 2026-03-14 update splitting the experiment into same-fold and cross-fold groups). This is an operational amendment recorded inline rather than via the `amendments:` field — a frontmatter anomaly worth flagging for the canonical-shape regularization pass.

### `t152-bpe-nda` — cleanest epistemic-arm shape

This is the closest seq-feats has to a vanilla epistemic-arm pre-reg:

> ### Primary Criterion (Confirmatory)
> For each model (DNABERT-2, NT-v2): CpG k-mers in promoter regions show statistically lower mean total_influence than CpG k-mers in intergenic regions.
> - Test: one-sided Mann-Whitney U (alternative="less")
> - Threshold: p < 0.025 per model (Bonferroni for 2 primary comparisons)
> - Decision: if both models pass → strong evidence NDA penetrates tokenization
> - Decision: if one model passes → suggestive, needs replication
> - Decision: if neither passes → tokenization blocks NDA for these architectures
>
> ### Null Result Plan
> If neither model passes the confirmatory criterion, treat BPE/6-mer tokenization as a likely barrier for NDA and keep per-nucleotide autoregressive models as the primary NDA path until a follow-up design justifies revisiting tokenized MLMs.

The decision criteria have three outcome buckets (both / one / neither), each mapping to a different epistemic update. The null-result plan is recast-spirit: "treat as a likely barrier... until a follow-up design justifies revisiting" — not a kill switch but a route-change with reopening conditions. **The author already wrote this in the recast's spirit.**

The hypothesis-portion targets `h01-raw-feature-embedding-informativeness` and `q84-does-nda-work-through-bpe-tokenization`. The pre-reg's commitment is genuinely about how to update belief in the q84 question (and through it, indirectly, h01) based on what the two models show. This is a real epistemic-arm pre-reg.

### `phase3b-validation` — phase-gate pre-reg

The title and frontmatter describe this as a **phase gate** — the criterion that determines whether the project moves from Phase 3B to Phase 3+. This is a different shape than the others:
- The `related:` field has hypothesis + questions (epistemic) but no entity-form `task:` refs (only a `task:` ref appears in `source_refs:`, in non-canonical form: `task:2026-03-11-phase3b`).
- The pre-reg's primary commitment is operational ("does Phase 3B's RF AUC reproduce within 0.01 of t120 results?") and binary (pass → proceed to Phase 3+; fail → block).

Under the recast, this is operationally-arm: a procedural commitment with a binary pass/fail gate. Honor it as such. The hypothesis-context in `related:` is for discoverability.

### `t138-cross-feature` and `t143-contextual-kmer` — mixed-design experiments

Both are similar in shape to `cycle1-domains` — multi-tier confirmatory designs with explicit AUC ranges and decision criteria. Both have hypothesis(es) + questions in `related:` for context. Both have task refs for the operational commitment. Same recurrent pattern as Issue 1.

---

## Plan-level issues surfaced

### Issue 1 (recurrent across all three projects so far): `related:` conflates commitment target with navigation context

Confirmed for the third time. seq-feats puts H01 in every pre-reg's `related:` — partly because H01 is the project's primary hypothesis and partly because the project lacks a separate `aboutness:` or `tags:` field that would otherwise carry the discoverability function.

(Note: seq-feats does have a `tags:` field on three of five pre-regs, but it's used for technical tags like `domains`, `protein`, `esm2`, `phase3plus` — not for hypothesis/question references.)

The natural-systems audit's recommended resolution applies: a sub-prompt at pre-reg authoring time to confirm which `related:` entries are commitment targets vs. context.

### Issue 2 (data-quality, pre-existing, not recast-specific): non-canonical frontmatter

All 5 seq-feats pre-regs predate the canonical pre-reg shape. Regularization is out of t012 scope but worth queuing.

The recast's `interpret-results` § 4d skill changes need to handle missing `committed:` gracefully (skip the temporal-anchoring step, still emit `bears_on`). This was already noted in natural-systems' audit Issue 4; confirmed here.

### Issue 3 (minor): mid-stream amendment without `amendments:` field

`cycle1-domains` records a 2026-03-14 amendment (same-fold/cross-fold split) in the body prose rather than via a structured `amendments:` field. Under operational-pre-reg semantics, this is a procedural amendment that should be in `amendments:`. Pre-existing convention drift, not a recast issue.

---

## Recommended actions

### For seq-feats

1. **No file edits required for the recast itself.**
2. **Author confirmation requested** (cross-project consistency): for the four operational-leaning pre-regs (cycle1-domains, phase3b-validation, t138-cross-feature, t143-contextual-kmer), confirm whether the H01 in `related:` is a commitment target or navigation context. The audit's expectation is "context" for all four; t152-bpe-nda is the lone genuine commitment-target pre-reg.
3. **Frontmatter regularization** (out of t012 scope): canonical-shape migration for all 5 pre-regs (`id:`, `type:`, `committed:`, `status:` from canonical vocabulary). Worth queuing as a separate cleanup task; none of these are blocking the recast.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Confirms Issue 1 across three projects.** Resolution is unchanged from natural-systems' audit — add the sub-prompt at pre-reg authoring time.
2. **Confirms Issue 4 from natural-systems' audit:** `interpret-results` must handle missing `committed:` gracefully. Make this explicit in the skill changes.
3. **No new plan-level issues from seq-feats.**

---

## Open questions for project owner

1. For each operational-leaning pre-reg (cycle1-domains, phase3b-validation, t138-cross-feature, t143-contextual-kmer): is the H01 reference in `related:` a commitment target ("we commit to interpreting this experiment as supporting/disputing H01 in this specific way") or navigation context ("this experiment touches H01, and the actual commitment is to the experiment design")?
2. Are the 5 pre-regs' non-canonical frontmatter shapes a known pre-existing issue, and is canonical-shape migration on a roadmap somewhere?
3. Does the project have any tooling that depends on `status: active` (non-canonical) being recognized? (None obvious in audit; please confirm.)

---

## Cross-project pattern (after natural-systems + protein-landscape + seq-feats)

Three projects, 22 pre-regs reviewed. The recurrent pattern is unchanged:

- **`related:` conflation** is universal: every project surveyed uses `related:` for both commitment targets and navigation context. The recast's resolution (sub-prompt at authoring time) is needed; without it, the recast's auto-derivation rule will produce `bears_on` edges that don't faithfully reflect the author's commitment.
- **Falsification-clause language is benign** when read as anti-bias procedural rigor — the recast preserves these naturally.
- **Frontmatter regularity varies by project**: protein-landscape has fully canonical frontmatter, natural-systems is mixed (most canonical, three minimal), seq-feats is uniformly minimal. The recast must handle missing `committed:` gracefully across all of them.
- **Pure-operational pre-regs are still rare** (none seen in any of the three projects so far). Every audited pre-reg has at least one epistemic target.

---

## What's next

After seq-feats sign-off, proceed to:
- 3d-attention-bias (4 pre-regs, mixed targets)
- cats (0 pre-regs, brief completeness note)
