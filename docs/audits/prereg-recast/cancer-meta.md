# Pre-registration recast audit — cancer/meta

**Audit date:** 2026-05-04
**Project root:** `~/d/cancer/meta` (= `/mnt/ssd/Dropbox/cancer/meta`)
**Scope:** federation umbrella project; 0 local pre-regs, but inherits / federates pre-reg conventions from children
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

`cancer/meta` is a **federation umbrella project** with 0 local pre-regs. Its role is to own cross-project synthesis, the materialized federated graph, and operating conventions; child projects (multiple-myeloma, cbioportal, mechanisms/evolution, conditions/pre-cancer) retain ownership of their local pre-regs.

The federation matters for the recast in two ways:

1. **`cancer/meta/validate.sh`** is the federation validator and inherits the standard pre-reg validation rules from `science-tool` (warns on missing `committed:` and `spec:`; recognizes both `doc/meta/pre-registration-<slug>.md` and `doc/pre-registrations/<slug>.md` placements). The recast does not change validation; it changes interpretation. So `validate.sh` doesn't need editing for t012.

2. **`cancer/meta/knowledge/graph.trig`** is the federated graph — 32 pre-reg identifiers from across the children appear there (sample: `pre-registration:t077-glmm-logit-pooling` from cbioportal, `pre-registration:h003-t002-ecdna-selection` from evolution, `pre-registration:2026-04-12-t172-scrna-per-cell-validation` from multiple-myeloma). Under the recast, the new `bears_on` auto-derivation rule (Prerequisite 2 of the recast plan) needs to fire correctly during the federated `graph build` so the federation-level graph picks up the new edges from each child's pre-regs. This is a code-side concern (the federation builder must inherit the deriver from `science-tool`) and not a meta-specific authoring concern.

**Recommendation for cancer/meta:** no file edits. Federation-level concerns are addressed via the recast's existing code prerequisites; no meta-specific tweak needed.

The meta audit also surfaced one item worth flagging in the recast plan: **federation pre-reg discoverability**. See § "Plan-level issues surfaced".

---

## Inventory

| File | Pre-regs | Notes |
|---|---|---|
| (none) | 0 | `cancer/meta` does not own pre-regs |

The 32 `pre-registration:` identifiers in the federated graph are children's pre-regs surfaced for cross-project querying. The federation does not author its own.

---

## Federation-aware findings

### `validate.sh` (federation validator)

`cancer/meta/validate.sh` lines 573–594 inherit the standard pre-reg validation:

```bash
# Path conventions:
#   doc/meta/pre-registration-<slug>.md  (natural-systems, protein-landscape, cbioportal)
#   doc/pre-registrations/<slug>.md      (mm30 canonical)
for f in "$DOC_DIR/meta/pre-registration-"*.md "$DOC_DIR/pre-registrations/"*.md; do
    ...
    if [ "$pre_type" = "pre-registration" ]; then
        # warns on missing `committed:` and `spec:`
```

The "mm30 canonical" comment confirms that **multiple-myeloma uses the `doc/pre-registrations/<slug>.md` placement** (mm30 is multiple-myeloma's earlier name). natural-systems, protein-landscape, and cbioportal use `doc/meta/pre-registration-<slug>.md`.

The recast's `interpret-results` § 4d skill changes need to lookup pre-regs from both paths. The audit's recommended path-scan command should include both:

```bash
ls doc/meta/pre-registration-*.md doc/pre-registrations/*.md 2>/dev/null
```

— which is what the recast draft already specifies. Confirmed correct.

### Federated graph

The federated graph (`cancer/meta/knowledge/graph.trig`) carries pre-reg identifiers from all children. Under the recast's Prerequisite 2 (auto-derivation of `bears_on` from pre-reg `related:` to epistemic targets), each child's `graph build` produces local `bears_on` edges. The federation's `graph build` is downstream of the children's; if it inherits the deriver implementation from `science-tool` (which it should — the federation builder is just `science-tool graph build` invoked at the federation root), the recast's edges propagate without federation-specific work.

The recast's draft does not explicitly call out federation behavior, but the assumption that "code prerequisites land in `science-tool` and federation inherits" is implicit. Worth flagging to make explicit.

### `cancer/meta`'s task list

`cancer/meta/tasks/active.md` includes a "multiple-myeloma routing" item to create a child-owned follow-up. This is **operational** (not a pre-reg, but the same shape: a procedural commitment about creating a question/plan in a downstream project). No recast impact.

---

## Plan-level issues surfaced

### Issue 1 (medium, new): federation pre-reg discoverability

`cancer/meta/knowledge/graph.trig` contains 32 pre-reg identifiers from children. Under the recast's auto-derivation rule, each pre-reg with an epistemic target produces a local `bears_on` edge in its child's graph. When the federated graph rolls up, these edges should appear at the federation level too — but only if (a) the federation builder runs the deriver and (b) the children's epistemic targets are also surfaced in the federated graph.

This isn't a recast-substance issue; it's a federation-implementation concern. Worth confirming with whoever maintains `cancer/meta`'s graph-build pipeline:

1. Does the federated `graph build` invoke the `bears_on` deriver (after Prerequisite 2 lands)?
2. Are children's epistemic entities (hypotheses, questions, propositions) federated into `cancer/meta`'s graph, so pre-reg → epistemic-target edges have a target to point to in the federated layer?

Likely both are yes by default (federation = `science-tool graph build` at meta root), but worth asserting in the recast plan rather than assuming.

### Issue 2 (minor): "mm30 canonical" comment is stale

The `validate.sh` comment refers to multiple-myeloma by its earlier name "mm30". This is a pre-existing convention drift, not a recast issue, but worth flagging during the inevitable cleanup pass.

---

## Recommended actions

### For cancer/meta

1. **No file edits required.**
2. **Confirm with maintainer**: the federation `graph build` will inherit the recast's `bears_on` deriver from `science-tool` once Prerequisite 2 lands; no meta-specific configuration needed.
3. **Pre-existing**: "mm30" → "multiple-myeloma" comment cleanup in `validate.sh`. Out of t012 scope.

### For the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`)

1. **Add a federation note** in § "Code prerequisites" or § "Sequencing for landing": "Federation builders inherit the `bears_on` deriver from `science-tool`; no per-federation configuration required. Pre-reg → epistemic-target edges propagate to the federated graph automatically once Prerequisite 2 lands."

2. **Update the missing-myeloma footnote.** The recast draft's § Status notes "myeloma is not a locally-present Science project" — that was wrong. Multiple-myeloma is at `~/d/cancer/cancer-types/multiple-myeloma/` with **30 pre-regs** (more than any other project surveyed). Update the footnote to reflect the correct path and pre-reg count, and the downstream-impact table to include it.

---

## Open questions for project owner

1. Is the federation `graph build` already configured to invoke `science-tool`'s deriver, or does it use a custom build step that would need updating to pick up the recast's new derivation rule?
2. Are children's epistemic entities (hypotheses, propositions) surfaced in `cancer/meta/knowledge/graph.trig`, so pre-reg → epistemic-target edges have valid targets at the federation level?

---

## What's next

After cancer/meta sign-off, proceed to:
- multiple-myeloma (30 pre-regs — biggest audit)
- data-sources/cbioportal (2 pre-regs)
- mechanisms/evolution (2 pre-regs)
- 3d-attention-bias (4 pre-regs, Science cluster)
- cats (0 pre-regs, brief completeness note)
