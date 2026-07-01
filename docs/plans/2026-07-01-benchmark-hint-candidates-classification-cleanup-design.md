# Benchmark Hint Candidates Classification Cleanup Design

## Context

`science benchmark hint-candidates` now exposes unmapped terms that may deserve benchmark facet hints. A first run across active projects showed two separate problems:

- The generated review artifacts defaulted to `docs/audits/...`, regardless of whether a project primarily uses `doc/` or `docs/`, and left uncommitted files in project repos.
- The domain-candidate bucket still contains terms that are not good benchmark facet candidates, including project shorthand (`mm30`, `pais`) and generic prose terms (`our`, `all`, `beyond`, `conjecture`, `organizing`).

This slice is limited to presentation and classification cleanup. It must not add new benchmark hint mappings.

## Goals

- Make `--write-review-file` use the project's canonical documentation directory.
- Keep report writes explicit and durable by default, while avoiding accidental git noise in the wrong path.
- Improve term categorization so obvious project-local or generic terms stop appearing as `domain-candidate`.
- Preserve the current deterministic, local-first evidence flow.
- Keep the JSON/table contract additive or behavior-preserving for existing fields.

## Non-Goals

- Do not add new `FACET_HINT_TERMS` entries for terms such as `cytogenetic`, `bulk`, `mutation`, `signature`, or `driver`.
- Do not introduce embeddings, fuzzy matching, or semantic classification.
- Do not auto-commit generated project reports from the command.
- Do not convert hint-candidate review artifacts into first-class science entities in this slice.

## Review Artifact Path

The command remains read-only unless `--write-review-file` is passed. When writing the default review file, use the same canonical path resolver as other science code:

- `resolve_paths(project_root).doc_dir`

The default path becomes:

```text
<doc-root>/audits/benchmark-hint-candidates/YYYY-MM-DD-<project>.yaml
```

For examples:

```text
~/d/cancer/cancer-types/multiple-myeloma/doc/audits/benchmark-hint-candidates/2026-07-01-multiple-myeloma.yaml
~/d/health/processes/post-acute-infection/doc/audits/benchmark-hint-candidates/2026-07-01-post-acute-infection.yaml
```

This intentionally removes the benchmark command's bespoke `docs/` hardcode. If the project-wide path policy ever needs to support `docs/`-only projects, that change belongs in the shared path resolver, not in this command.

Custom `--output` continues to resolve under the project root and must not escape it. If a caller wants a non-versioned report, they can pass an ignored path explicitly, but the default is a durable project audit artifact.

The command should still print the resolved path to stderr after a successful write. It should never silently create a review file.

## Existing Generated Files

The exploratory files generated under `docs/audits/benchmark-hint-candidates/` in active projects should be treated as disposable output, because they were written before the canonical path rule existed. Cleanup is a one-off operator step, not command behavior: remove only those generated files, and only when they are still untracked. Unrelated project changes must not be touched.

After the path fix ships, durable review artifacts can be regenerated under the convention-respecting location and committed in the relevant project if we decide they are useful records.

## Classification Cleanup

The existing evidence report remains the source of truth. `benchmark_hint_candidates_report()` should continue projecting over `gaps_report(..., evidence_report=True)` rather than re-tokenizing project text or benchmark metadata.

### Category Rules

The term buckets should remain mutually exclusive:

1. `project-local`: project root leaf tokens, `science.yaml` project identity tokens, and entity id-stem tokens.
2. `workflow-or-modeling`: terms about the work process or modeling vocabulary rather than benchmark facets.
3. `domain-candidate`: remaining unmapped high-value terms that are plausible benchmark facet candidates.
4. `existing-hint`: only emitted when `--include-existing` is used; these rows enumerate already-mapped lexicon terms.

Precedence is `project-local` before `workflow-or-modeling` before `domain-candidate`.

### Generic Prose Terms

Route a small, explicit generic-term set into the existing `workflow-or-modeling` category, rather than adding a fifth suppression path. The active-project run showed these are not useful benchmark facets:

```text
all, beyond, conjecture, organizing, our, shared
```

These should not be emitted as `domain-candidate`. They should remain visible in JSON as `workflow-or-modeling` terms, while table output keeps focusing on domain candidates.

This list should stay small and evidence-driven. Do not fold it into `_UNMAPPED_TERM_EXCLUSIONS`, because that would make the terms disappear from the evidence report and weaken reviewability. Do not turn it into a broad stopword list that hides real scientific terms.

### Project Shorthand

Terms such as `mm30` and `pais` are project shorthand, not general benchmark facets. Avoid hardcoding active project names in the benchmark library as one-off exceptions.

Use project-owned metadata as the structural source for shorthand:

1. Treat the project root leaf tokens as project-local, as today.
2. Add tokens from `science.yaml` `name` and `id`.
3. Keep entity id-stem tokens project-local, as today.

Do not use `science.yaml` `tags` as an identity-token source. Tags often contain legitimate domain terms (`long-covid`, `dysautonomia`, `mutation`, `gene-expression`) and tokenizing them as project-local would suppress exactly the candidates this command is meant to surface.

This classifies `mm30` from `science.yaml` `name: mm30` and `cbioportal` from cBioPortal's project identity without embedding active-project exceptions in library code. `pais` should be handled through entity id-stem tokenization: if an entity id such as `proposition:0014-pais-small-fiber-structural-lesion-ienfd` contributes `pais` to the evidence side, the id-stem side should classify that token as project-local. If that does not currently happen, fix the id-stem tokenization rather than overloading tags. A term that cannot be classified from structured project identity or id-stems stays visible for human review.

Missing `science.yaml` should degrade to today's behavior: project root leaf tokens and entity id-stem tokens still apply. Malformed `science.yaml` should follow the existing path/config loader behavior rather than adding a command-specific fallback.

## Output Behavior

Default table output should continue showing only `domain-candidate` rows. JSON should continue including all categories and summary counts. The `lexicon_candidates` compatibility behavior is unchanged.

The summary should continue exposing `term_bucket_cap` and the truncation notice. If classification cleanup moves terms out of `domain-candidate`, `domain_candidate_terms` should decrease while `candidate_terms` may remain similar.

## Testing

Add focused tests for:

- default review path uses `resolve_paths(project_root).doc_dir`;
- default review path chooses `doc/` when both `doc/` and `docs/` exist;
- successful writes still print the resolved review path to stderr;
- generic prose terms do not appear as `domain-candidate`;
- generic prose terms remain visible as `workflow-or-modeling` terms;
- project shorthand from `science.yaml` `name` and `id` is categorized as `project-local`;
- project shorthand from split entity id-stems, including `pais` in `0014-pais-small-fiber`, is categorized as `project-local`;
- missing `science.yaml` still reports using project root leaf tokens and entity id-stems;
- category precedence remains deterministic and mutually exclusive;
- existing `--output` escape protections still hold.

Run the focused benchmark CLI/opportunity tests after implementation:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
```

## Success Criteria

- Running `science benchmark hint-candidates --write-review-file` writes under `resolve_paths(project_root).doc_dir / "audits" / "benchmark-hint-candidates"`.
- No default command creates untracked files in the command's former hardcoded `docs/audits/...` tree.
- Active-project `domain-candidate` tables are cleaner: project shorthand from project-owned metadata and generic prose terms are not prominent domain candidates.
- No new benchmark hint mappings are added.
