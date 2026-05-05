# Pre-registration recast migration audit - natural-systems

**Audit date:** 2026-05-04
**Migration date:** 2026-05-05
**Project root:** `/mnt/ssd/Dropbox/natural-systems`
**Migration branch:** `migration/prereg-recast-natural-systems`
**Scope:** all 14 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

natural-systems is the most pre-reg-heavy locally-present project. The original audit found that author practice already matched the recast's spirit: null results are informative rather than terminal, and the most prominent procedural amendment (`h07-beta-arbitration`) explicitly says it does not update the H07 verdict by itself.

The migration now makes that practice explicit in machine-readable metadata. Each pre-registration keeps broad `related:` links for navigation and context, and adds `commits_to:` only for the epistemic entities the body actually makes verdict-bearing, calibration-bearing, or threshold-bearing.

Executed changes:

- Added `commits_to:` to all 14 pre-registrations.
- Regularized the three minimal-frontmatter pre-registrations with `id`, `type`, `committed`, and `status`.
- Converted `pre-registration:t349` from `status: "active"` to `status: "committed"` because it has a locked `committed` date and is a registration record, not an indefinitely active lock.
- Added missing `status: "committed"` to committed-but-statusless `t214` and `t342`.
- Removed the project-local `pre-registration` extension kind from `knowledge/sources/project_specific/manifest.yaml`; the canonical recast kind now owns `pre-registration:*`.

---

## Migration Decisions

| File | Status after migration | `commits_to` targets | Context-only examples left in `related` |
|---|---|---|---|
| `pre-registration-h07-beta-arbitration.md` | draft | h07, q67 | q65, q69, tasks, discussion |
| `pre-registration-q54-temporal-profile.md` | committed | q54, q56 | none |
| `pre-registration-t085-t086.md` | committed | h01, h02 | literature synthesis |
| `pre-registration-t092.md` | committed | q52, q56 | t092 task, prior interpretation |
| `pre-registration-t214.md` | committed | h01, q83, q86 | t214 task, interpretations |
| `pre-registration-t333.md` | draft | h05, q92 | q23, chained pre-regs t342/t349/t353 |
| `pre-registration-t342.md` | committed | h01, h02, q95 | tasks and discussion |
| `pre-registration-t344.md` | complete/null | h01, h02, q95, q98, q99 | chained pre-reg t342, tasks |
| `pre-registration-t349.md` | committed | h01, q100 | h02, q95, q99, chained pre-regs t342/t344 |
| `pre-registration-t353.md` | complete | h02, q101 | h01, q75, q100, chained pre-reg t349 |
| `pre-registration-t371.md` | complete | h04, q72 | t371 task, prior interpretation |
| `pre-registration-t372.md` | complete | h02, q49 | t372 task, prior interpretations |
| `pre-registration-t403.md` | draft | h05, q92 | chained pre-reg t333, tasks, result interpretations |
| `pre-registration-t409.md` | complete | h03, q15, q70 | t370/t408/t409 tasks and interpretations |

The main judgment call was to avoid converting every epistemic `related:` entry into a commitment target. For example, `t349` names H02/q95/q99 because it follows the partition-null thread, but its body frames the live commitment as q100 plus H01 C6 calibration. Those remain related context, not direct `bears_on` targets.

---

## Graph Behavior

Validation confirms the recast behavior:

- `commits_to:` materializes as direct `sci:bearsOn`.
- `related:` remains broad `skos:related` context.
- Pre-reg-to-pre-reg chains do not become direct `sci:bearsOn` edges.
- Context-only epistemic refs such as h07 -> q65/q69, t349 -> H02/q95/q99, and t353 -> H01/q75/q100 remain discoverable without becoming prereg commitment targets.

Representative generated graph excerpts:

```ttl
<http://example.org/project/pre-registration/h07-beta-arbitration>
    sci:bearsOn
        <http://example.org/project/hypothesis/h07-empirical-fidelity-alignment>,
        <http://example.org/project/question/q67-beta-vs-research-attention> ;
    skos:related
        <http://example.org/project/question/q65-beta-predicts-lens-difficulty>,
        <http://example.org/project/question/q69-annotation-provenance-and-independence> .
```

```ttl
<http://example.org/project/pre-registration/t349>
    sci:bearsOn
        <http://example.org/project/hypothesis/h01-double-categorical-model-relationships>,
        <http://example.org/project/question/q100-fiber-membership-as-covering> ;
    skos:related
        <http://example.org/project/hypothesis/h02-enriched-categorical-lenses>,
        <http://example.org/project/question/q95-subset-meta-model-partition-selection>,
        <http://example.org/project/question/q99-within-fiber-sub-axis-privilege> .
```

---

## Validation

Commands run from the Science worktree:

```bash
uv run --frozen science-tool graph build --project-root /mnt/ssd/Dropbox/natural-systems/.worktrees/prereg-recast-natural-systems
uv run --frozen science-tool graph validate --path /mnt/ssd/Dropbox/natural-systems/.worktrees/prereg-recast-natural-systems/knowledge/graph.trig
```

Result:

- Graph build passed and wrote `knowledge/graph.trig`.
- Graph validation passed: `parseable_trig`, `provenance_completeness`, `causal_acyclicity`, and `orphaned_nodes`.
- Edge inspection found no direct `sci:bearsOn` target under `/pre-registration/`, confirming chained pre-reg references remain contextual.

---

## Residual Risk

This migration relies on body-text interpretation for the `commits_to` split. The chosen targets are conservative: if a future author wants a context-only epistemic link to become a commitment target, they should move that entity into `commits_to` rather than rely on `related`.

The pre-existing `build/` directory in the natural-systems main worktree was not touched.

---

## Next

natural-systems is ready for branch review and merge into its `main` once the project diff is accepted. Continue the prereg migration sequence with the remaining local projects after this branch lands.
