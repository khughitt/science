# Code → Task Back-Link Convention

> **Status callout.** Pattern 3 (descriptor sidecar field) names optional fields whose canonical schema is **pending Bucket C / P1 #8 namespace decision** (datapackage `<project>:` extension profile). Field names below are stable; if Bucket C namespaces them, this doc updates in lockstep.

This doc lists four sanctioned patterns for linking code or notebooks back to a task, question, hypothesis, or interpretation. The reverse direction (entity → code via `Files:` lists in plan and interpretation prose) remains primary; these patterns close the code-side gap where it is cheap. Adoption is per-project and per-artifact. None are validator-enforced upstream.

## When to use which pattern

Pick the lightest pattern that fits the artifact shape:

| Artifact shape | Recommended pattern |
| --- | --- |
| Notebook (Jupyter / marimo, 1-10 per project) | Pattern 1 — filename tag |
| Standalone analysis script that produces a tracked artifact | Pattern 3 — descriptor sidecar field |
| Standalone script where the filename can't carry the tag | Pattern 2 — comment-block header |
| Commit subject for any change to a script or notebook | Pattern 4 — commit-message tag (orthogonal to Patterns 1-3) |
| Library code under `src/<pkg>/` | None required |

## Pattern 1: Filename tag

Format: `<task-id>_<slug>.py` for tasks, `q<NNN>_<slug>.py` for questions, `h<NN>_<slug>.py` for hypothesis-scoped scripts. Multiple tags allowed via repeated prefix:

```text
t131_three_way_ranking_comparison.py
q011_length_adjustment_topn_comparison.py
q011_t070_compare.py
```

The slug after the tag is descriptive prose; the tag is the load-bearing part. Canonical example: cbioportal's three task-tagged marimo notebooks under `code/notebooks/`.

## Pattern 2: Comment-block header

Format: a single-line comment near the top of the script body, after the docstring or shebang:

```python
# task: t131
# task: t131, q011  # multiple tags allowed
```

Equivalent forms are sanctioned for non-`#` languages: `// task: tNNN`, `% task: tNNN`. Place after the module docstring; do not embed inside the docstring (keeps the docstring clean for help/tooling).

## Pattern 3: Descriptor sidecar field

For artifact-producer descriptor JSONs (e.g., protein-landscape's `descriptors/<artifact>.parquet.descriptor.json`), four optional fields are sanctioned on top of the existing `git_commit` / `command` / `parameters` / `inputs[]` / `outputs[]`:

```json
{
  "task": "t131",
  "question": "q011",
  "hypothesis": "h02",
  "interpretation": "i007"
}
```

Each field is optional and accepts either a string or a list (`"task": ["t131", "t070"]`). **Status: pending Bucket C / P1 #8 namespace decision** — when the datapackage `<project>:` extension profile lands, these field names become part of the canonical descriptor schema. They may end up at top level or under a `science:` block. Field names themselves are stable; only nesting may change. Projects already shipping descriptors (protein-landscape today, 19 files) MAY adopt the field names early.

## Pattern 4: Commit-message tag

Format: Conventional-Commits-style with the task id in the scope:

```text
fix(t131): thread random_seed through ranking pipeline
feat(t128): retroactive datapackage manifests
fix(t131,q011): ...      # multiple tags via comma
```

Both audit projects that use this pattern (cbioportal and protein-landscape) enforce shape project-side via `commitlint.config.mjs` + a `.husky/commit-msg` hook; that enforcement is not standardized here. This pattern is **orthogonal** to Patterns 1-3 — a single commit may touch a notebook with Pattern 1 and a script with Pattern 2, and the commit-tag still applies independently.

## Non-rules

- None of these patterns are validator-enforced upstream. Project-side commitlint is fine for Pattern 4.
- Adoption is per-project and per-artifact; mixing patterns within a project is fine.
- Library code (e.g., `src/<pkg>/`) does not need any of these.
- The reverse direction (entity → code via plan / interpretation `Files:` lists) remains primary; these conventions only close the code-side gap where it is cheap.

## See also

- [`../project-organization-profiles.md`](../project-organization-profiles.md) — Code → Task Back-Link section.
- [`../audits/downstream-project-conventions/synthesis.md`](../audits/downstream-project-conventions/synthesis.md) §6.4, §8.2 — evidence base from the four-project audit.
- [`README.md`](README.md) — directory scope and entry bar.
