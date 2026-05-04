# Pre-registration recast audit — cats

**Audit date:** 2026-05-04
**Project root:** `/mnt/ssd/Dropbox/cats`
**Scope:** completeness — 0 pre-regs
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

cats is a `profile: software` project (a "biological sequence visualization, annotation, and analysis CLI tool") with **0 pre-regs**. The audit is included for completeness across the surveyed cluster.

cats is a software-aspect project rather than a research-aspect project. It uses the same `science-tool` infrastructure but does not author hypothesis tests or pre-registrations. The recast has **no impact** on cats today.

**Recommendation for cats:** No action needed.

If cats ever grows hypothesis-driven research components (e.g., empirical claims about motif-detection accuracy or k-mer statistics), the recast's behavior will apply naturally — no special-case handling required.

---

## Inventory

| File | Pre-regs |
|---|---|
| (none) | 0 |

---

## Federation status

cats is **not** part of the cancer federation (it's a Science cluster project, not a cancer cluster project). It uses `profile: software` rather than `profile: research`, which signals to `science-tool` that some research-oriented validations don't apply. Pre-reg conventions don't apply either.

---

## What's next

This is the final per-project audit. Cumulative coverage:

- **9 projects audited** (8 Science cluster + cancer cluster, plus cats for completeness): natural-systems, protein-landscape, seq-feats, cancer/meta, multiple-myeloma, cbioportal, mechanisms/evolution, 3d-attention-bias, cats.
- **60 pre-regs reviewed** across 7 pre-reg-using projects (natural-systems 14, protein-landscape 3, seq-feats 5, multiple-myeloma 30, cbioportal 2, mechanisms/evolution 2, 3d-attention-bias 4).
- **0 pre-regs** in cancer/meta, conditions/pre-cancer (skipped per user), and cats.

Next: consolidated revision of the recast plan (`docs/plans/2026-05-04-prereg-recast-draft.md`) incorporating all surfaced findings.

The plan revisions to apply (per cumulative audit state):

1. **Reclassify `inquiry` from `REFERENCE` to `EPISTEMIC`** in Prerequisite 1. Per agreed mm Issue 2 resolution.
2. **Add the sub-prompt at pre-reg authoring time** to distinguish commitment targets from navigation context. Per universal `related:` conflation finding.
3. **Add prose for hypothesis-in-body-only pre-regs** in `interpret-results` § 4d. Per mm Issue 1, strengthened by cbioportal.
4. **Document unregistered-kinds silent-skip behavior** with a recommended health-check pattern. Per cumulative cross-project finding.
5. **Add federation note** in § "Code prerequisites" — federated graph builders inherit the `bears_on` deriver. Per cancer/meta audit.
6. **Update missing-myeloma footnote** — multiple-myeloma is at `~/d/cancer/cancer-types/multiple-myeloma/` with 30 pre-regs (more than any other project surveyed).
7. **Update downstream-impact table** to reflect the full surveyed corpus (60 pre-regs across 7 projects: ns 14, pl 3, sf 5, mm 30, cb 2, ev 2, 3dab 4).
8. **Add proposition-and-evidence-model.md doc note** — the new subsection introduced by the recast needs to classify `inquiry` as EPISTEMIC and add it to the list of entity kinds participating in `bears_on`.

After these revisions, the recast plan is ready for downstream-maintainer circulation.
