# Cohort-Scoped Curation Capabilities — Plan

**Driver:** the `natural-systems` design
`doc/plans/2026-07-16-plan-corpus-curation-design.md` §3.2 (two gaps) and §3.3
(delivery gate). That design is the authority for the requirements; this file
records what landed here.

## What landed (v0.4.0)

1. **Id allowlist** on `entities archive` and `entities mark-superseded`
   (`--id` repeatable, `--ids-from FILE`). Authoritative: the operation acts on
   exactly the enumerated ids. On `mark_superseded` it narrows BOTH `to_mark`
   and `to_repair`, because both are committed by the same prepare loop; graph
   validation stays corpus-wide.
2. **`entities import`** — proposes an id for a loose markdown document,
   validates the prospective write, relocates it, repoints references in both
   directions, and runs a post-move link/anchor/reference audit inside the
   transaction. A durable preview: `--save-plan` writes the plan, `--apply-plan`
   replays it by identity (no re-derivation, no `--apply` flag).
3. **`reference_rewrite`** — the substituting counterpart to
   `entities._remove_frontmatter_ref`, over frontmatter refs,
   `relations[].target`, and semantically-resolved markdown links. `apply`
   replays a frozen plan with per-file preimage hashes rather than rescanning.
4. **`markdown_scan`** — prose-versus-literal scanning, so a link inside a code
   fence is treated as the example it is, not rewritten or audited as a live
   reference.
5. **`text_scan`** — the scannable-text surface, so a corpus-wide pass does not
   die on the first PNG, and code files are surfaced for manual handling.
6. **`propose_number` / `claim_number_in_dir`** — read-only archive-aware id
   proposal, and an atomic claim of an exact previewed number that re-checks the
   archive under its sentinel.
7. **transaction machinery** — a whole-tree snapshot (bytes, mode, symlink
   target, and directory existence) with rollback asserted by tree identity.

## v0.4.1 — scan size ceiling

The v0.4.0 corpus scan filtered candidate files by directory and suffix but not
size. Pointed at a real research repo whose `data/` holds an 800 MB `.json`, the
reference scanner read that file into a `str` and ran the link regex over it,
ballooning a single `entities import` to tens of GB of RSS. `text_scan`
`iter_scannable_files` now excludes any file over `MAX_SCANNABLE_BYTES` (5 MiB)
as a third exclusion alongside skip-dirs and the suffix allowlist — a data
artifact is categorically not a reference site, and the read is the harm. The
ceiling sits far above the largest hand-authored source (a sub-megabyte
canonical yaml), so the guard never clips a genuine reference file. The guard is
in `iter_scannable_files`, not `read_text_or_skip`, deliberately: a size-based
`Skip` would surface in `audit_moved_references` as a "may reference" problem,
and any audit problem rolls the apply back — so every apply against a
data-bearing repo would abort. Direct reads of specific known files (the imported
document, a resolved link target) stay uncapped, so importing a legitimately
large document still works.

## Known gaps left open, deliberately

- `_remove_frontmatter_ref` still ignores `relations[].target` while
  `archive._inbound_live_refs` reads it. `reference_rewrite` handles both, but
  fixing the remover changes `entity remove` behaviour and belongs in its own
  change with its own tests.
- `_next_numeric_local_part` (`entities.py:610`) remains unlocked and
  archive-blind. `create_entity` still uses it; only the import path is fixed.
  Making `create_entity` use `propose_number`/`claim_number_in_dir` is a
  behaviour change for every kind and needs its own review.
- `claim_number_in_dir` re-reads the archive under its sentinel, closing the
  preview-to-claim window. It does not make claim-versus-archival atomic: a
  concurrent `archive_entities` could still land between the check and the
  `open(..., "x")`. Closing that needs a lock shared across both commands --
  a cross-command concurrency design, not a patch. Residual exposure is
  microseconds between two local file operations rather than the minutes a human
  spends reading a report. **This residual is not detected by `science validate`:**
  a live number equal to an archived one produces distinct canonical ids, so the
  archive-collision check (`archive.py:337`) is silent, and number hygiene
  (`entity_conformance.py:147`) globs live files only. Detection across
  live+archived numeric prefixes, or the shared lock, is deferred to plan 2 --
  not relied on here.
- `audit_moved_references` skips code files when checking inbound references.
  They are reported as `ManualHit`s by the rewriter, but the audit cannot resolve
  a path that may be constructed at runtime, so it cannot fail loudly on one
  without failing on every dynamic path in the repository. Code references remain
  a human's responsibility, surfaced but not gated.
- `markdown_scan` is a scanner, not a CommonMark parser. It does not model HTML
  blocks or link reference definitions (`[id]: path`). Neither appears as a
  reference site in the current corpus; if one is added, it would be scanned as
  prose. A parser upgrade (`markdown-it-py`) is the exit if that changes.
- The masking bias is conservative in ONE direction only: a genuinely live
  reference hidden inside a masked construct (a deep indented block, an
  ambiguously-fenced region) is neither rewritten nor reported as a `ManualHit` --
  `prose_only` manual scanning skips masked regions so that fenced examples do not
  become per-run noise. The failure mode is a stale link, not corrupted prose, and
  the post-move audit surfaces broken prose links; but an audit that is itself
  prose-only cannot see a link buried in a masked construct. Making masked mentions
  into `ManualHit`s (without reintroducing fenced-example noise) is a `markdown_scan`
  refinement deferred until a real corpus reference is found to hide this way.
- The 5 MiB scan ceiling (v0.4.1) means a reference genuinely living inside a
  file larger than that -- a multi-MB generated artifact, say -- is neither
  rewritten nor surfaced by the post-move audit, exactly as a reference inside a
  code file or a skipped directory is not. In this corpus every hand-authored
  reference site is sub-megabyte, so the ceiling only ever excludes data and
  generated output; if a real reference is one day found in an oversized file,
  the exit is a streaming line-scan that never materialises the whole file,
  rather than raising the cap.
- The scan-exclusion fix covers a plan applied against its OWN corpus: apply
  excludes the plan file it was handed. A DIFFERENT stale plan `.json` left lying
  in the corpus from an earlier, unrelated import would still be scanned as prose
  and could contribute a spurious old-path mention. The durable-preview machinery
  in plan 2 owns a conventional out-of-corpus (or globally-excluded) plan location;
  until then, the operator convention is to delete a saved plan once applied.
