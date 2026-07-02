# Science Framework Surface Audit

**Date:** 2026-07-01

**Scope:** The Science framework's user-facing command surface, durable
documentation set, and internal CLI/framework structure. This audit is a
read-only synthesis pass: it records evidence, risks, and recommended cleanup
threads before any behavioral refactor.

## Artifacts

- [`command-inventory.md`](command-inventory.md) records the current CLI shape and
  naming/organization observations.
- [`docs-coherence.md`](docs-coherence.md) reviews how the current user guide,
  conventions, and process docs sit together.
- [`framework-findings.md`](framework-findings.md) captures design debt and data
  model/API tightening opportunities.
- [`flag-drift.md`](flag-drift.md) records concrete CLI option drift against the
  CLI behavior convention.
- [`backlog.md`](backlog.md) ranks follow-up cleanup and implementation slices.

## Summary

Science now has a broad and useful framework surface, but it has grown through
many successful local additions rather than one deliberate command taxonomy. The
current CLI exposes 46 top-level commands, 48 command groups, and 253 leaf
commands. That scale is manageable, but only if the command families, docs, and
internal helpers make the common workflows easy to understand.

The strongest next move is not a rewrite. It is a curation and consistency pass:
extract a durable CLI/workflow map, identify legacy or experimental surfaces,
normalize repeated command patterns, and split the largest framework files only
where clear domain boundaries already exist.

## Main Findings

1. The user guide is now a real manual, but it lacks a command-oriented index.
   `docs/user-guide/agent-workflows.md` maps user intents to agent workflows and
   selected CLI commands; it does not explain the CLI taxonomy or which command
   families are canonical, legacy, experimental, or migration-only.

2. Several command names encode historical layers rather than user concepts.
   The clearest examples are `dataset`, `datasets`, `data-package`, `data`, and
   `commons dataset`. The docs explain some distinctions, but the top-level CLI
   help presents them as peers.

3. `science/src/science_tool/cli.py` is the largest Python file in the framework
   at about 8k lines. Some domains are already split into focused CLI modules
   (`annotate`, `commons`, `dag`, `validate`, `big-picture`, `curate`), so there
   is an established migration pattern for shrinking the root CLI without
   inventing a new architecture.

4. Repeated command semantics are not visibly documented as a contract. Common
   patterns include report-then-apply, dry-run/apply, JSON/table output, project
   root resolution, stale graph warnings, migration commands, and "writes source
   files, not graph" behavior. These should be promoted to a framework-level
   convention before broad refactoring.

5. The docs contain valuable plan-derived knowledge, but some convention docs
   have become mini-guides while some user-guide chapters contain convention
   material. This is not harmful yet, but it makes future updates harder unless
   the guide gets a stronger "where this belongs" rule.

## Recommended Next Slice

Start with a docs-first command taxonomy:

1. Add a durable CLI/workflow map under `docs/user-guide/`.
2. Mark each command family as canonical, specialized, derived-state,
   migration-only, exploratory, or legacy.
3. Use that map to nominate the first low-risk CLI consistency cleanup.

The best first code cleanup after that is likely extracting one coherent command
family from `science/src/science_tool/cli.py` where the domain already has clear
module boundaries and focused tests.

## Follow-Up Status

The first docs slice from this audit now lives in
[`../../user-guide/cli-and-workflows.md`](../../user-guide/cli-and-workflows.md).
It adds the command taxonomy, write classes, dataset command distinction,
source-authored vs graph-authored guidance, and shared CLI behavior notes.
The taxonomy is now guarded by `science/tests/test_user_guide_docs.py`, which
checks the guide against the registered top-level Click commands.
