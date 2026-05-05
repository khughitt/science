# Pre-registration recast migration audit - protein-landscape

**Audit date:** 2026-05-04
**Migration date:** 2026-05-05
**Project root:** `/mnt/ssd/Dropbox/protein-landscape`
**Migration branch:** `migration/prereg-recast-protein-landscape`
**Scope:** all 3 pre-regs under `doc/meta/pre-registration-*.md` (worktree duplicates excluded)
**Recast spec:** `docs/plans/2026-05-04-prereg-recast-draft.md` (revision 2)

---

## Summary

protein-landscape has three pre-registrations. Two (`q63`, `q81`) are discriminating tests between H02 and H03 readings; one (`t098`) is mostly a methodology lock with two explicit question-level primary tests.

The migration applies the post-recast framing used in the other projects:

- `related:` remains broad navigation and context.
- `commits_to:` names only the epistemic entities the pre-registration directly commits to testing or calibrating.
- Existing falsification language is treated as an anti-bias procedural lock, not as an indefinite epistemic lock. The resulting evidence remains responsive to upstream data, feature, and uncertainty changes.

Executed changes:

- Added `commits_to:` to all 3 pre-registrations.
- Added `status: "committed"` to all 3 committed-but-statusless pre-registrations.
- Removed the project-local `pre-registration` extension kind from `knowledge/sources/local/manifest.yaml`; the canonical recast kind now owns `pre-registration:*`.

---

## Migration Decisions

| File | Status after migration | `commits_to` targets | Context-only examples left in `related` |
|---|---|---|---|
| `pre-registration-q63-heldout-taxa-benchmark.md` | committed | q63, h02, h03 | execution tasks, design discussion |
| `pre-registration-q81-curator-derived-non-structural.md` | committed | q81, h02, h03 | q63, t145 interpretation, post-t145 discussion, t169 |
| `pre-registration-t098-phylogenetic-2m.md` | committed | q11, q14 | t098/t074 tasks, pilot interpretations, F43, bias-audit task |

Notes:

- `q63` commits directly to the benchmark-discrimination question and the two hypotheses whose readings it distinguishes.
- `q81` is a follow-up to q63, but its fresh commitment is the q81 curator-derived non-structural benchmark plus the H02/H03 readings it calibrates. q63 stays contextual.
- `t098` explicitly says the actual registration is a methodology lock, then names three primary tests. The two project questions (`q11`, `q14`) are direct commitment targets. `finding:F43` remains contextual because the body uses it as motivation and methodology discipline rather than as a direct result-pattern commitment.

---

## Graph Behavior

Validation confirms that `commits_to:` is accepted by the project graph build and materializes the intended direct commitment targets.

Representative depth-1 commitment edges:

```ttl
<http://example.org/project/pre-registration/q63-heldout-taxa-benchmark>
    sci:bearsOnTarget
        <http://example.org/project/question/q63-heldout-taxa-benchmark-discrimination>,
        <http://example.org/project/hypothesis/h02-hierarchical-sparse-archetypes>,
        <http://example.org/project/hypothesis/h03-data-driven-primacy> .
```

```ttl
<http://example.org/project/pre-registration/q81-curator-derived-non-structural>
    sci:bearsOnTarget
        <http://example.org/project/question/q81-archetype-vs-label-on-curator-derived-non-structural>,
        <http://example.org/project/hypothesis/h02-hierarchical-sparse-archetypes>,
        <http://example.org/project/hypothesis/h03-data-driven-primacy> .
```

```ttl
<http://example.org/project/pre-registration/t098-phylogenetic-2m>
    sci:bearsOnTarget
        <http://example.org/project/question/q11>,
        <http://example.org/project/question/q14> .
```

Important graph nuance: protein-landscape already has provenance and closure paths that can make a pre-registration appear in the transitive `sci:bearsOn` list for downstream discussions or questions. Those are graph-derived dependency paths, not extra `commits_to` entries. The direct migration question is whether the explicit prereg commitments are present and whether pre-reg-to-pre-reg chains are avoided; both conditions hold.

---

## Validation

Commands run from the Science worktree:

```bash
uv run --frozen science-tool graph build --project-root /mnt/ssd/Dropbox/protein-landscape/.worktrees/prereg-recast-protein-landscape
uv run --frozen science-tool graph validate --path /mnt/ssd/Dropbox/protein-landscape/.worktrees/prereg-recast-protein-landscape/knowledge/graph.trig
```

Result:

- Graph build passed and wrote `knowledge/graph.trig`.
- Graph validation passed: `parseable_trig`, `provenance_completeness`, `causal_acyclicity`, and `orphaned_nodes`.
- Edge inspection found no direct pre-reg-to-pre-reg `sci:bearsOn` targets.

---

## Residual Risk

The only judgment-sensitive mapping is `t098`: its body mentions F43-derived propositions, but the frontmatter only has a `finding:F43` identifier rather than durable proposition IDs. The migration keeps F43 contextual and commits directly to q11/q14. A later proposition cleanup could add explicit proposition entities if the project wants finer-grained prereg commitment targets.

The dirty `protein-landscape/main` worktree was not touched; this migration was done in an isolated worktree.

---

## Next

protein-landscape is ready for branch review and merge into its `main` once the project diff is accepted.
