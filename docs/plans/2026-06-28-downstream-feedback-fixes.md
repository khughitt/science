# Downstream feedback fixes — 2026-06-28

Resolution record for the `science feedback` batch dated 2026-06-28 (plus the
2026-06-27 positive item). All code lives under `~/d/science/science/`; tests in
`~/d/science/science/tests/`. Run with `cd ~/d/science/science && uv run --no-sync pytest`.

User-confirmed scope: implement the **6 tractable** items now; **defer** fb-014
and fb-004 (see below). Branch: `fix/feedback-2026-06-28`.

---

## Shipped

### fb-2026-06-28-008 — prose-lint short-form IDs ignore archived task aliases
**target:** command:prose-lint · **category:** gap · **project:** multiple-myeloma

Archived tasks live only in `tasks/archive.md`; the graph TaskAdapter deliberately
skips that file, so archived IDs never reached the short-form resolver and a prose
mention of `t075` was flagged as a style violation.

- `prose_lint.py`: new `_archived_task_aliases(root)` reads archive declarations via
  `refs._load_task_ids` and maps `t<NN> -> task:t<NN>`; `build_short_form_resolver`
  merges them (`setdefault`, so live entities win).
- Tests: `TestArchivedTaskAliases` in `test_prose_lint.py`.

### fb-2026-06-28-009 — numeric-anchor flags internal cross-references
**target:** command:validate · **category:** gap · **project:** multiple-myeloma

The numeric-claim regex only matches floats / ≥3-digit ints, so the real false
positives were dotted refs like `Figure 3.2`, `Section 4.1`, `Equation 2.3`, `§4.2`,
and ≥3-digit `Table 100`.

- `prose_lint.py`: new `_CROSS_REFERENCE_RE` (Section/Sec/Chapter/Figure/Fig/Table/
  Tbl/Equation/Eq/Appendix/Panel/§ + dotted/ranged number, word-boundary anchored;
  `§` handled outside the `\b` branch). `detect_numeric_anchor` skips any numeric
  match falling inside a cross-reference span. A real claim beside a ref (e.g. the
  `47%` in `Figure 3.2 reports the 47% improvement`) still flags.
- Tests: cross-reference cases in `TestNumericAnchor`.

### fb-2026-06-28-010 — frontmatter-inline-gap ignores project shorthand aliases
**target:** command:validate · **category:** gap · **project:** multiple-myeloma

A `related: [multiple-myeloma]` entry mentioned in the body as `mm30` was flagged
as an unmentioned gap.

- `prose_lint.py`: `detect_frontmatter_inline_gaps` gains an `alias_map` param; a
  `related:` entry is satisfied if the body contains any spelling equivalent under
  the alias map (canonical ↔ alias). `scan_root` threads the existing resolver
  (already an alias map) into this check.
- `validate/checks/prose_lints.py`: build the resolver when **either**
  `short-form-ids` or `frontmatter-inline-gap` is enabled.
- Tests: alias cases in `TestFrontmatterInlineGap`.

### fb-2026-06-28-012 — review-books skill names a validator-rejected subdir
**target:** command:review-books · **category:** friction · **project:** natural-systems

Skill text said chapter notes go in `entities/books/<citekey>/`, but the validator
rejects subdirs under entity-kind dirs; subagents, the book template, and the
validator all use `doc/books/<citekey>/`. Docs were wrong, validator correct.

- `commands/review-books.md` and `codex-skills/science-review-books/SKILL.md`:
  chapter notes + part rollups now `doc/books/<citekey>/`; the overview entity
  stays `entities/books/<citekey>.md`.
- `templates/book.md`: synced the root mirror to the packaged model template
  (`../../doc/books/<citekey>/chNN-*.md`); the two are now byte-identical.

### fb-2026-06-28-013 — stale lifted-marker sidecars hang validate
**target:** command:validate / markers scan --ignore-lifted · **category:** friction · **project:** multiple-myeloma

A stale sidecar selector misses on exact match and falls through to the fuzzy
fallback, which scans the whole document per window — O(windows·n·max_distance).
On a ~1.2 MB source this did not return within 20 s.

- `annotation/selector.py`: `_FUZZY_MAX_COMPARISONS` cost ceiling; `_fuzzy_unique_match`
  bails to "no match" (→ SUPERSEDED) when the estimated comparison budget is
  exceeded. Fuzzy is best-effort recovery, so a stale sidecar now surfaces the
  marker instead of silently hiding it (and the scan no longer hangs).
- Tests: `test_fuzzy_guard_skips_pathological_inputs` (instant on ~1.2 MB) +
  `test_fuzzy_still_recovers_on_normal_sized_source` (guard doesn't disable
  legitimate recovery).

### fb-2026-06-28-015 — verify-access result buried under audit warnings
**target:** command:catalog-datasets · **category:** friction · **project:** multiple-myeloma

`science dataset verify-access` printed every pre-existing project-wide audit
failure before the one actionable result line.

- `cli.py`: print the `entity -> access=… runtime=…` line **first**; pre-existing
  (unrelated) audit failures collapse to a single summary note pointing at
  `science validate`. New `--show-preexisting` flag restores the per-line listing.
- Tests: `test_cli_verify_access_collapses_preexisting_warnings` +
  `test_cli_verify_access_show_preexisting_lists_them`.

---

## Deferred (user decision)

### fb-2026-06-28-014 — gap-scan floods with internal/methodological no-candidate flags
**target:** command:catalog-datasets · **project:** multiple-myeloma

Deferred to a dedicated **brainstorming** session. User intuition: the root cause is
**upstream in how questions are formulated**, not in the scan. The right framing is
"what is the ideal long-term system, what is the gap today, and what signals/
incentives steer curation toward it" — not a one-off filter on the scan output.

### fb-2026-06-28-004 — data/ ignore boundary orphans durable evidence records
**target:** module:data_worktree · **project:** natural-systems

Deferred to its own effort. A full design already exists at
`docs/plans/2026-06-28-feedback-data-evidence-tracking-boundary.md` with open
questions (evidence-path convention shape, single source of truth for the
policy + size threshold, optional validate-time warn). Multi-part (convention +
size-guard pre-commit hook + `science data audit`), not a quick fix.

---

## No action

### fb-2026-06-27-003 — pre-register §1b caught a load-bearing data-definition error
**target:** command:pre-register · **category:** positive · **project:** pan-disease

Positive confirmation that pre-register §1b ("load real artifacts before locking")
works as intended. No change.
